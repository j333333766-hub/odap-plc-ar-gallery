# 회전체 AR 갤러리 · 수학교사 전문적학습공동체 사례발표용(11/5) — 인하대 특강 갤러리(inha-ar-gallery) build.py 를 고친 것
#   ① 연수용 제출 폴더(SRC)에서 11/5 이후 올라온 ZIP 만 '전학공 선생님' 작품, ② 학교 원래 제출 폴더(REF_SRC)에서는 1학년 6~10반만(반별 묶음).
#   python build.py            ← 제출 폴더의 ZIP 을 모두 풀어 works/ 와 첫 화면(index.html)을 새로 만든다
#   python build.py <폴더>     ← 다른 폴더의 ZIP 으로
# - ZIP 은 그림판3D 의 '저장 → AR 웹뷰어 (ZIP)' 결과(index.html·model.glb·model.usdz). 이 셋만 꺼낸다.
# - 하위 폴더 속 ZIP·압축을 풀어 둔 폴더도 읽는다(같은 학번이 이미 있으면 건너뜀).
# - 작품마다 works/<파일 이름>/ 에 풀고, 뷰어 위쪽에 작품 이름과 '← 작품 목록' 을 넣는다.
# - 첫 화면은 ZIP 개수만큼 파일 이름 버튼. 고친 뒤 git add -A → commit → push 하면 1~2분 뒤 Pages 에 반영.
import hashlib, html, io, json, re, shutil, subprocess, sys, zipfile
from pathlib import Path
from urllib.parse import quote
import segno

BASE = 'https://j333333766-hub.github.io/odap-plc-ar-gallery/'   # Pages 주소(QR 에 들어감)


def qr_svg(url):
    """스마트폰으로 바로 여는 QR(흰 바탕 SVG, 어두운 화면에서도 읽히게)."""
    b = io.BytesIO()
    segno.make(url, error='m').save(b, kind='svg', scale=1, border=2, dark='#000', light='#fff',
                                    xmldecl=False, svgns=True, omitsize=True)
    return b.getvalue().decode('utf-8')

ROOT = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r'C:\Users\j333333\OneDrive - 구월중학교\2026학년도\회전체 만들기 3D 모델 제출(연수용)')   # 연수생이 올리는 곳 → 모두 '인하대 특강'
REF_SRC = Path(r'C:\Users\j333333\OneDrive - 구월중학교\2026학년도\회전체 만들기 3D 모델 제출')   # 학교 원래 제출 폴더 → 참고 반만
WORKS = ROOT / 'works'
NEED = ('index.html', 'model.glb', 'model.usdz')
REF_CLASSES = ('106', '107', '108', '109', '110')   # 참고로 보일 학생 반(학번 앞 세 자리) — 사용자 11/4: 학습 자료는 6~10반만
from datetime import datetime
PLC_SINCE = datetime(2026, 11, 5, 15, 30)   # 연수용 폴더에서 이 시각 이후에 올라온 파일만 전학공 작품(11/4 인하대 파일은 뺌)


def label(zip_path):
    """보여 줄 이름과 폴더 이름. 공개 사이트라 '10101홍길동' → ('10101 홍*동', '10101'): 이름은 가운데를 가리고 폴더는 학번만(10/29 사용자 결정)."""
    import unicodedata
    stem = unicodedata.normalize('NFC', zip_path.stem)   # 11/4 맥·아이패드에서 올린 파일은 한글이 풀어쓴(NFD) 꼴이라 이름 가림을 빠져나갔다
    s = re.sub(r'[_ ]*(AR ?)?웹 ?뷰어$', '', stem).strip(' _') or stem
    s = re.sub(r'^\W+', '', s) or s   # '❤️10912홍길동'처럼 앞에 붙은 이모지·기호는 떼야 이름이 가려진다
    m = re.match(r'^(\d{4,6})[\s_-]*([가-힣]{2,5})', s)
    if not m:
        # '10626wjsdudwls'처럼 한글 이름을 영문 자판으로 친 경우도 이름이라 학번만 보인다
        m = re.match(r'^(\d{5})[\s_-]*[A-Za-z]', s)
        if m:
            return m[1], m[1]
        r = re.fullmatch(r'([가-힣]{2,5}?)+', s)   # '김다은김다은김다은'처럼 이름을 되풀이한 것
        if r:
            s = r[1]
        if re.fullmatch(r'[가-힣]{2,5}', s):   # 11/4 이름만 쓴 연수생 파일도 가린다
            return (s[0] + '*' if len(s) == 2 else s[0] + '*' * (len(s) - 2) + s[-1]), 'name'
        if re.search(r'[가-힣]', s):   # 그 밖에 한글이 섞인 이름은 혹시 실명일 수 있어 첫·끝 글자만 남기고 폴더는 'name'
            return s[0] + '*' * max(1, len(s) - 2) + (s[-1] if len(s) > 2 else ''), 'name'
        return s, s
    sid, nm = m.groups()
    masked = nm[0] + '*' if len(nm) == 2 else nm[0] + '*' * (len(nm) - 2) + nm[-1]
    return f'{sid} {masked}', sid


def slug(name, used):
    s = re.sub(r'[\\/:*?"<>|#%&{}\s]+', '_', name).strip('_.') or 'work'
    base, n = s, 2
    while s in used:
        s, n = f'{base}_{n}', n + 1
    used.add(s)
    return s


def patch_viewer(text, name, url):
    """뷰어 위쪽: 왼쪽 '← 작품 목록', 가운데 작품 이름, 오른쪽 '📱 휴대폰으로' (누르면 이 작품 주소 QR)."""
    t = html.escape(name)
    text = re.sub(r'<title>.*?</title>', f'<title>{t} · AR로 보기</title>', text, count=1, flags=re.S)
    side = 'position:absolute;top:50%;transform:translateY(-50%);color:inherit;font:inherit;font-size:14px;font-weight:600;text-decoration:none;opacity:.9;padding:8px 6px;line-height:20px'
    back = f'<a href="../../" style="{side};left:14px">← 작품 목록</a>'
    phone = (f'<button type="button" style="{side};right:14px;background:none;border:0;cursor:pointer;padding:0" '
             "onclick=\"document.getElementById('wb-qr').hidden=false\">📱 휴대폰으로</button>")
    box = ('<div id="wb-qr" hidden onclick="this.hidden=true" style="position:fixed;inset:0;z-index:10;background:rgba(0,0,0,.6);'
           'display:grid;place-items:center;cursor:pointer"><div style="background:#fff;color:#15151c;border-radius:16px;padding:18px;'
           f'text-align:center;width:min(300px,86vw)">{qr_svg(url)}<p style="margin:10px 0 0;font-size:14px;line-height:1.5">'
           f'스마트폰 카메라로 찍으면<br><b>{t}</b> 작품이 열려요.<br><span style="color:#667">아무 곳이나 누르면 닫혀요</span></p></div></div>'
           '<style>#wb-qr[hidden]{display:none!important}</style>')
    text = re.sub(r'<header>.*?</header>', f'<header style="position:relative">{back}{t}{phone}</header>{box}', text, count=1, flags=re.S)
    return re.sub(r'alt="[^"]*"', f'alt="{t}"', text, count=1)


# 지난 결과 지우기. OneDrive 가 동기화 중이면 폴더 지우기가 거부되므로 파일만 지우고 폴더는 되는 만큼만 지운다
# (남은 빈 폴더는 git 이 올리지 않으니 사이트에 영향 없음)
WORKS.mkdir(exist_ok=True)
for f in sorted(WORKS.rglob('*'), key=lambda p: -len(p.parts)):
    try:
        f.unlink() if f.is_file() else f.rmdir()
    except OSError:
        pass
items, used, skipped = [], set(), []


def add_work(src, read):
    """src: 이름을 딸 ZIP(또는 폴더) 경로, read(k): NEED 파일 k 의 내용."""
    g = CUR
    name, key = label(src)
    if g == 'ref':
        if key[:3] not in REF_CLASSES:
            return
        g = 'c' + key[:3]
    if g == 'plc':
        try:
            if datetime.fromtimestamp(src.stat().st_mtime) < PLC_SINCE:
                return
        except OSError:   # 풀어 둔 폴더는 src 가 가짜 .zip 경로 → 폴더 시각으로
            if datetime.fromtimestamp(src.with_suffix('').stat().st_mtime) < PLC_SINCE:
                return
        # 연수용 폴더에 남아 있는 학생 사본(원래 제출 폴더에 같은 이름이 있는 것)은 연수생 작품이 아니므로 뺀다
        try:
            top_name = src.relative_to(SRC).parts[0]
        except ValueError:
            top_name = src.name
        if (REF_SRC / top_name).exists() or (REF_SRC / (top_name + '.zip')).exists():
            return
        key = 'plc-' + key   # 선생님 작품이 학생 폴더와 겹치지 않게
    d = WORKS / slug(key, used)
    d.mkdir(exist_ok=True)
    for k in NEED:
        data = read(k)
        if k == 'index.html':
            data = patch_viewer(data.decode('utf-8'), name, f'{BASE}works/{quote(d.name)}/').encode('utf-8')
        (d / k).write_bytes(data)
    size = sum((d / k).stat().st_size for k in NEED)
    items.append({'name': name, 'dir': d.name, 'mb': round(size / 1e6, 1), 'g': g})


def scan(SRC):
    # 1) 제출 폴더 바로 아래 ZIP (원래 방식: 같은 학번 ZIP 이 둘이면 둘 다 카드가 생김)
    # 2) 학생이 만든 하위 폴더 속 ZIP 과, ZIP 을 풀어 둔 폴더(index.html·model.glb·model.usdz 가 바로 들어 있는 폴더)
    #    — 1)에 이미 있는 학번(같은 이름)이면 건너뛴다(친구 ZIP 을 자기 폴더에 함께 넣은 경우가 많음)
    top = sorted(SRC.glob('*.zip'), key=lambda p: p.name)
    sub = sorted((p for p in SRC.rglob('*.zip') if p.parent != SRC), key=lambda p: (len(p.parts), str(p)))
    loose = sorted((p for p in SRC.rglob('*') if p.is_dir() and all((p / k).is_file() for k in NEED)), key=str)
    for z in top + sub:
        rel = z.relative_to(SRC).as_posix()
        if z.parent != SRC and slug(label(z)[1], set()) in used:
            skipped.append(f'{rel} (같은 작품이 이미 있음)')
            continue
        try:
            with zipfile.ZipFile(z) as zf:
                names = {Path(i.filename).name: i for i in zf.infolist() if not i.is_dir()}
                if not all(k in names for k in NEED):
                    skipped.append(f'{rel} (AR 웹뷰어 ZIP 이 아님: {", ".join(k for k in NEED if k not in names)} 없음)')
                    continue
                add_work(z, lambda k: zf.read(names[k]))
        except zipfile.BadZipFile:
            skipped.append(f'{rel} (ZIP 파일이 깨짐)')
    for p in loose:
        rel = p.relative_to(SRC).as_posix()
        # 폴더 이름이 '학번이름' 꼴이면 그 이름으로. Path('11001 강이원.zip') 처럼 넘겨 label() 을 그대로 쓴다
        src = p.with_name(p.name + '.zip')
        if slug(label(src)[1], set()) in used:
            skipped.append(f'{rel}/ (풀어 둔 폴더, 같은 작품이 이미 있음)')
            continue
        add_work(src, lambda k: (p / k).read_bytes())



# 11/4: 연수용 폴더(연수생 작품) → 학교 원래 폴더(참고 반)
for CUR, folder in (('plc', SRC), ('ref', REF_SRC)):
    scan(folder)

# 미리보기 사진(thumb.webp): model.glb 내용이 같으면 _thumbcache/ 에 둔 사진을 다시 쓰고, 새 모델만 thumbs.mjs 로 찍는다
CACHE = ROOT / '_thumbcache'
CACHE.mkdir(exist_ok=True)
jobs = []
for it in items:
    d = WORKS / it['dir']
    it['h'] = hashlib.sha1((d / 'model.glb').read_bytes()).hexdigest()[:16]
    c = CACHE / f"{it['h']}.webp"
    if c.exists():
        shutil.copyfile(c, d / 'thumb.webp')
    else:
        jobs.append({'glb': f"works/{it['dir']}/model.glb", 'out': f"works/{it['dir']}/thumb.webp"})
if jobs:
    jf = CACHE / 'jobs.json'
    jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding='utf-8')
    subprocess.run(['node', str(ROOT / 'thumbs.mjs'), str(jf)], cwd=ROOT)
    jf.unlink()
for it in items:
    t = WORKS / it['dir'] / 'thumb.webp'
    it['thumb'] = t.exists()
    if t.exists():
        shutil.copyfile(t, CACHE / f"{it['h']}.webp")
    del it['h']

items.sort(key=lambda i: (i['g'] != 'plc', i['g'], i['dir']))   # 선생님 작품 먼저, 다음 반 순서
total = sum(i['mb'] for i in items)
data = json.dumps(items, ensure_ascii=False).replace('<', '\\u003c')
page = (ROOT / 'page.tpl.html').read_text(encoding='utf-8').replace('__ITEMS__', data).replace('__QR__', qr_svg(BASE)).replace('__URL__', BASE)
(ROOT / 'index.html').write_text(page, encoding='utf-8')
print(f"전학공 {sum(i['g'] == 'plc' for i in items)}개 + 학생 {sum(i['g'] != 'plc' for i in items)}개 · " + f'작품 {len(items)}개 · {total:.1f}MB' + (f' · 건너뜀 {len(skipped)}개' if skipped else ''))
for s in skipped:
    print('  건너뜀:', s)
if total > 800:
    print('  ⚠ GitHub Pages 사이트 한도(1GB)에 가까워요. 반별로 저장소를 나누세요.')
