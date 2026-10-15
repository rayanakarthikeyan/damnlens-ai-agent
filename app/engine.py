"""Deterministic extraction orchestration; document content is always treated as data."""
from __future__ import annotations

import hashlib
import re
import statistics
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import pymupdf as fitz

OCR_LOCK = Lock()
_ocr = None
HEADER_WORDS = {'date', 'description', 'amount', 'balance', 'quantity', 'qty', 'price', 'total',
                'debit', 'credit', 'sku', 'item', 'account', 'reference', 'tax', 'net', 'unit', 'id', 'region'}


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def norm(value):
    return re.sub(r'[^a-z0-9]', '', clean(value).lower())


def number(value):
    """Parse unambiguous decimal amounts; preserve identifiers in the exporter."""
    text = clean(value).replace('−', '-').replace('\u00a0', '')
    if not text or text in {'-', '—', 'N/A'}:
        return None
    negative = text.startswith('(') and text.endswith(')')
    text = re.sub(r'^(?:USD|INR|EUR|GBP)\s*', '', text, flags=re.I)
    text = re.sub(r'[$₹€£%()\s]', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.') if text.rfind(',') > text.rfind('.') else text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '') if re.fullmatch(r'-?\d{1,3}(,\d{3})+', text) else text.replace(',', '.')
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', text):
        return None
    result = float(text)
    return -result if negative else result


def is_header(row):
    filled = [c for c in row if clean(c)]
    words = set(re.findall(r'[a-z]+', ' '.join(filled).lower()))
    return len(words & HEADER_WORDS) >= 2 and sum(number(c) is not None for c in filled) < len(filled) * .4


def unique_headers(row):
    counts = Counter()
    result = []
    for i, c in enumerate(row):
        c = clean(c) or f'Column {i + 1}'
        counts[c] += 1
        result.append(c if counts[c] == 1 else f'{c} ({counts[c]})')
    return result


def record(cells, page, bbox, method, confidence=1.0):
    return {'cells': [clean(c) for c in cells], 'page': page, 'bbox': [round(float(x), 2) for x in bbox],
            'method': method, 'confidence': round(float(confidence), 3)}


def native_tables(page, page_no):
    candidates = page.find_tables(strategy='lines_strict').tables
    method = 'Native PDF · grid'
    if not candidates:
        candidates = page.find_tables(strategy='text', min_words_vertical=3, min_words_horizontal=1).tables
        method = 'Native PDF · text alignment'
    out = []
    for table in candidates:
        raw = table.extract()
        if table.col_count < 2 or len(raw) < 2:
            continue
        rows = []
        if table.header.external:
            rows.append(record(table.header.names, page_no, table.header.bbox, method))
        for idx, cells in enumerate(raw):
            if any(clean(c) for c in cells):
                rows.append(record(cells, page_no, table.rows[idx].bbox, method))
        if len(rows) >= 2:
            out.append({'rows': rows, 'bbox': list(table.bbox), 'width': page.rect.width})
    return out


def ocr_words(image):
    global _ocr
    with OCR_LOCK:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            model_dir=Path(__file__).resolve().parents[1]/'models'
            _ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2,
                            rec_model_path=str(model_dir/'en_PP-OCRv3_rec_infer.onnx'),
                            rec_keys_path=str(model_dir/'en_dict.txt'))
        # Page orientation is preserved; per-word 180-degree classification can
        # incorrectly flip short headers such as "Tax %".
        result, _ = _ocr(image,use_cls=False)
    words=[]
    for box,text,score in (result or []):
        bbox=[min(p[0] for p in box),min(p[1] for p in box),max(p[0] for p in box),max(p[1] for p in box)]
        words.append({'bbox':bbox,'text':text,'score':score})
    return words


def clusters(values, tolerance=8):
    groups = []
    for v in sorted(values):
        if not groups or v - statistics.mean(groups[-1]) > tolerance:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [statistics.mean(g) for g in groups]


def scan_tables(page, page_no, dpi=220):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    # Correct modest scan skew before both text recognition and grid detection.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    lines = cv2.HoughLinesP(bw, 1, np.pi / 1800, 100, minLineLength=image.shape[1] // 4, maxLineGap=20)
    angles = []
    for line in ([] if lines is None else np.asarray(lines).reshape(-1,4)):
        x1, y1, x2, y2 = line
        angle = np.degrees(np.arctan2(y2-y1, x2-x1))
        if abs(angle) < 7:
            angles.append(angle)
    angle = statistics.median(angles) if angles else 0
    transform = cv2.getRotationMatrix2D((image.shape[1]/2, image.shape[0]/2), angle, 1)
    if abs(angle) > .15:
        image = cv2.warpAffine(image, transform, (image.shape[1], image.shape[0]), borderValue=(255,255,255))
    inverse = cv2.invertAffineTransform(transform) if abs(angle) > .15 else np.array([[1,0,0],[0,1,0]])
    words = ocr_words(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1,max(30,image.shape[1]//25)),np.uint8))
    v = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((max(30,image.shape[0]//30),1),np.uint8))
    grid = cv2.dilate(cv2.bitwise_or(h,v), np.ones((3,3),np.uint8))
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    scale = 72/dpi

    def original_box(box):
        pts = np.array([[[box[0],box[1]], [box[2],box[1]], [box[2],box[3]], [box[0],box[3]]]], dtype=np.float32)
        pts = cv2.transform(pts, inverse)[0] * scale
        return [float(pts[:,0].min()),float(pts[:,1].min()),float(pts[:,0].max()),float(pts[:,1].max())]

    out = []
    for contour in sorted(contours, key=lambda c: cv2.boundingRect(c)[1]):
        x,y,w,height = cv2.boundingRect(contour)
        if w < image.shape[1]*.25 or height < 50:
            continue
        xs = clusters((np.where((v[y:y+height,x:x+w]>0).sum(axis=0) > height*.45)[0]+x).tolist())
        ys = clusters((np.where((h[y:y+height,x:x+w]>0).sum(axis=1) > w*.45)[0]+y).tolist())
        if len(xs)<3 or len(ys)<3:
            continue
        rows = []
        for top,bottom in zip(ys,ys[1:]):
            cells, scores = [], []
            for left,right in zip(xs,xs[1:]):
                selected = [a for a in words if left <= (a['bbox'][0]+a['bbox'][2])/2 < right
                            and top <= (a['bbox'][1]+a['bbox'][3])/2 < bottom]
                selected.sort(key=lambda a: (round(a['bbox'][1]/12),a['bbox'][0]))
                cells.append(' '.join(a['text'] for a in selected))
                scores.extend(a['score'] for a in selected)
            if any(cells):
                rows.append(record(cells,page_no,original_box([xs[0],top,xs[-1],bottom]),'OCR · grid',statistics.mean(scores) if scores else 0))
        if rows:
            out.append({'rows':rows,'bbox':original_box([x,y,x+w,y+height]),'width':page.rect.width})
    if out:
        return out
    # Borderless fallback anchors columns to the densest aligned text line.
    line_centers = clusters([(a['bbox'][1]+a['bbox'][3])/2 for a in words], tolerance=12)
    lines = [[a for a in words if abs((a['bbox'][1]+a['bbox'][3])/2-y)<12] for y in line_centers]
    lines = [sorted(line,key=lambda a:a['bbox'][0]) for line in lines if len(line)>=2]
    if not lines:
        return []
    anchor = max(lines,key=len)
    starts = [a['bbox'][0] for a in anchor]
    rows=[]
    for line in lines:
        cells=['']*len(starts)
        for a in line:
            idx=min(range(len(starts)),key=lambda i:abs(starts[i]-a['bbox'][0]))
            cells[idx]=clean(cells[idx]+' '+a['text'])
        box=[min(a['bbox'][0] for a in line),min(a['bbox'][1] for a in line),max(a['bbox'][2] for a in line),max(a['bbox'][3] for a in line)]
        rows.append(record(cells,page_no,original_box(box),'OCR · inferred columns',min(a['score'] for a in line)))
    return [{'rows':rows,'bbox':[0,0,page.rect.width,page.rect.height],'width':page.rect.width}]


def stitch(fragments):
    tables=[]
    for frag in fragments:
        rows=frag['rows']
        first=rows[0]['cells']
        has_header=is_header(first)
        headers=unique_headers(first) if has_header else [f'Column {i+1}' for i in range(len(first))]
        data=rows[1:] if has_header else rows
        previous=tables[-1] if tables else None
        same_schema=previous and len(previous['headers'])==len(headers)
        if same_schema and has_header:
            matches=sum(SequenceMatcher(None,norm(a),norm(b)).ratio()>.82 for a,b in zip(previous['headers'],headers))
            same_schema=matches/len(headers)>=.8
        elif same_schema:
            # Headerless continuation requires adjacent pages and matching horizontal span.
            same_schema=rows[0]['page']==previous['pages'][-1]+1 and abs(frag['bbox'][0]/frag['width']-previous['_x'])<.04 and abs((frag['bbox'][2]-frag['bbox'][0])/frag['width']-previous['_w'])<.04
        adjacent=previous and rows[0]['page']==previous['pages'][-1]+1
        if same_schema and adjacent:
            target=previous
            target['headers_removed']+=int(has_header)
        else:
            target={'id':len(tables)+1,'name':f'Table {len(tables)+1}','headers':headers,'rows':[], 'pages':[],
                    'headers_removed':0,'inferred_headers':not has_header,'_x':frag['bbox'][0]/frag['width'],
                    '_w':(frag['bbox'][2]-frag['bbox'][0])/frag['width']}
            tables.append(target)
        for row in data:
            if [norm(c) for c in row['cells']]==[norm(c) for c in target['headers']]:
                target['headers_removed']+=1
                continue
            row['cells']=(row['cells']+['']*len(headers))[:len(headers)]
            row['id']=len(target['rows'])+1
            target['rows'].append(row)
        target['pages']=sorted(set(target['pages']+[r['page'] for r in rows]))
    for t in tables:
        t.pop('_x'); t.pop('_w')
    return tables


def validate(tables):
    issues=[]
    def add(t,kind,message,row=None,col=None,severity='warning'):
        issues.append({'id':len(issues)+1,'table':t['id'],'row':row,'column':col,'kind':kind,'severity':severity,'message':message})
    for t in tables:
        rows=t['rows']; headers=t['headers']; n=len(headers)
        if t.get('inferred_headers'):
            add(t,'header_review','Headers could not be identified. Generic column names need review.')
        if rows and any('inferred' in r['method'] for r in rows):
            add(t,'alignment_review','Borderless OCR column positions were inferred. Verify alignment against the source.')
        seen={}
        numeric_cols=[]
        normal_rows=[r for r in rows if not any(re.fullmatch(r'(?:grand\s+|sub\s*)?total(?:\s*[:\-])?',c,re.I) for c in r['cells'][:3])]
        dense_cols=[c for c in range(n) if normal_rows and sum(bool(r['cells'][c]) for r in normal_rows)/len(normal_rows)>=.9]
        for c,h in enumerate(headers):
            values=[r['cells'][c] for r in rows if r['cells'][c]]
            if not values:
                add(t,'empty_column',f'Column "{h}" is completely empty.',col=c+1)
            if values and sum(number(v) is not None for v in values)/len(values)>.7:
                numeric_cols.append(c)
        sums={c:0 for c in numeric_cols}; sum_counts={c:0 for c in numeric_cols}
        section_sums={c:0 for c in numeric_cols}; section_counts={c:0 for c in numeric_cols}
        for r in rows:
            cells=r['cells']; rid=r['id']
            key=tuple(cells)
            if key in seen:
                add(t,'duplicate_row',f'Identical to row {seen[key]}; preserved for review.',rid)
            seen[key]=rid
            if r['confidence']<.88:
                add(t,'low_ocr',f'OCR recognition score {r["confidence"]:.0%}; check source.',rid)
            if sum(bool(c) for c in cells)<n*.4:
                add(t,'sparse_row','Most cells are empty; possible merged or shifted row.',rid)
            total=any(re.fullmatch(r'(?:grand\s+|sub\s*)?total(?:\s*[:\-])?',c,re.I) for c in cells[:3])
            grand_total=any(re.fullmatch(r'grand\s+total(?:\s*[:\-])?',c,re.I) for c in cells[:3])
            for c in numeric_cols:
                value=number(cells[c])
                if total:
                    expected_sum=sums[c] if grand_total else section_sums[c]
                    expected_count=sum_counts[c] if grand_total else section_counts[c]
                    if value is not None and expected_count and abs(value-expected_sum)>max(.02,abs(expected_sum)*.00001):
                        add(t,'total_mismatch',f'{headers[c]}: stated {value:,.2f}; preceding rows sum to {expected_sum:,.2f}.',rid,c+1,'error')
                elif value is not None:
                    sums[c]+=value; sum_counts[c]+=1;section_sums[c]+=value;section_counts[c]+=1
                elif cells[c]:
                    add(t,'column_type',f'Non-numeric value in mostly numeric column "{headers[c]}".',rid,c+1)
            if total:
                section_sums={c:0 for c in numeric_cols};section_counts={c:0 for c in numeric_cols}
            if not total:
                for c in sorted(set(numeric_cols+dense_cols)):
                    if not cells[c]:
                        add(t,'missing_value',f'Missing value in usually populated column "{headers[c]}".',rid,c+1)
            keys=[norm(h) for h in headers]
            qty=next((i for i,h in enumerate(keys) if h in {'quantity','qty'}),None)
            price=next((i for i,h in enumerate(keys) if h in {'unitprice','price','rate'}),None)
            net=next((i for i,h in enumerate(keys) if h in {'net','subtotal','lineamount'}),None)
            if not total and None not in (qty,price,net):
                q,p,v=[number(cells[i]) for i in (qty,price,net)]
                if None not in (q,p,v) and abs(q*p-v)>.02:
                    add(t,'arithmetic',f'Quantity × unit price = {q*p:,.2f}; {headers[net]} is {v:,.2f}.',rid,net+1,'error')
            tax=next((i for i,h in enumerate(keys) if h in {'tax','taxamount'} and '%' not in headers[i]),None)
            line_total=next((i for i,h in enumerate(keys) if h in {'total','linetotal','gross'}),None)
            if not total and None not in (net,tax,line_total):
                net_value,tax_value,total_value=[number(cells[i]) for i in (net,tax,line_total)]
                if None not in (net_value,tax_value,total_value) and abs(net_value+tax_value-total_value)>.02:
                    add(t,'line_total',f'Net + tax = {net_value+tax_value:,.2f}; total is {total_value:,.2f}.',rid,line_total+1,'error')
            # Validate running bank balance only when an explicit opening balance exists.
            balance=next((i for i,h in enumerate(keys) if h=='balance'),None)
            debit=next((i for i,h in enumerate(keys) if h in {'debit','withdrawal'}),None)
            credit=next((i for i,h in enumerate(keys) if h in {'credit','deposit'}),None)
            if rid>1 and None not in (balance,debit,credit) and not total:
                before=number(rows[rid-2]['cells'][balance]); after=number(cells[balance])
                d=number(cells[debit]); cr=number(cells[credit])
                if None not in (before,after) and (d is not None or cr is not None):
                    expected=before-(d or 0)+(cr or 0)
                    if abs(expected-after)>.02:
                        add(t,'balance_mismatch',f'Expected running balance {expected:,.2f}; found {after:,.2f}.',rid,balance+1,'error')
    return issues


def extract(path: Path, progress=lambda *a:None, force_ocr=False):
    start=time.perf_counter()
    doc=fitz.open(path)
    try:
        if doc.needs_pass:
            raise ValueError('Password-protected PDFs are not supported. Upload an unlocked copy.')
        if not doc.is_pdf:
            pdf=fitz.open('pdf',doc.convert_to_pdf()); doc.close(); doc=pdf
        if not 1<=len(doc)<=50:
            raise ValueError('Documents must contain 1–50 pages.')
        fragments=[]; pages=[]
        for i,page in enumerate(doc):
            progress(i,len(doc),f'Inspecting page {i+1}')
            native=len(page.get_text().strip())>=25 and not force_ocr
            attempts=[]; found=[]
            if native:
                try:
                    found=native_tables(page,i+1)
                    attempts.append('native')
                except Exception as exc:
                    attempts.append(f'Native extraction failed: {type(exc).__name__}; retried with OCR')
            if not found:
                progress(i,len(doc),f'OCR on page {i+1}')
                attempts.append('ocr')
                try:
                    found=scan_tables(page,i+1)
                except Exception as exc:
                    attempts.append(f'OCR failed: {type(exc).__name__}: {str(exc)[:160]}')
            fragments.extend(found)
            pages.append({'page':i+1,'tables':len(found),'method':'ocr' if 'ocr' in attempts else 'native',
                          'attempts':attempts,'status':'extracted' if found else 'needs_review'})
            progress(i+1,len(doc),f'Page {i+1} complete')
        tables=stitch(fragments)
        issues=validate(tables)
        for p in pages:
            if p['status']=='needs_review':
                issues.append({'id':len(issues)+1,'table':None,'row':None,'column':None,'kind':'page_review','severity':'error',
                               'message':f'Page {p["page"]}: no table extracted. Inspect the page; output may be incomplete.'})
        return {'filename':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'page_count':len(doc),
                'pages':pages,'tables':tables,'issues':issues,'elapsed_seconds':round(time.perf_counter()-start,2),
                'row_count':sum(len(t['rows']) for t in tables),'headers_removed':sum(t['headers_removed'] for t in tables),
                'engine':'LedgerLens 1.0 · PyMuPDF + RapidOCR (PP-OCR / ONNX)','edits':[]}
    finally:
        doc.close()
