"""Paired local same-screenshot target-lookup benchmark.

Measures screenshot preparation, scripted OCR callback, target scoring and
proposal construction. Neither condition captures the desktop, invokes real
Windows OCR, hosts an LLM, clicks, or verifies an app action.
"""
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
import json
import sys
import time

from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tavi_compact import propose, propose_batch


def main():
    with TemporaryDirectory() as folder:
        image=Path(folder)/'screenshot.png'
        im=Image.new('RGB',(1280,720),'white')
        draw=ImageDraw.Draw(im)
        words=[]
        for i in range(8):
            label=f'Button{i}'
            x=50+(i%4)*295
            y=60+(i//4)*180
            draw.rectangle((x,y,x+215,y+65),fill='#222222')
            words.append(dict(text=label,x=x+30,y=y+15,width=110,height=31))
        im.save(image)
        im.close()
        queries=[dict(id=str(i),task=f'Press Button{i}',target=f'Button{i}') for i in range(8)]
        calls={'one':0,'batch':0}
        def ocr_one(_):
            calls['one']+=1
            return dict(status='available',words=words)
        def ocr_batch(_):
            calls['batch']+=1
            return dict(status='available',words=words)
        one_times,batch_times=[],[]
        parity=True
        for round_no in range(12):
            def one():
                start=time.perf_counter()
                result=[propose(image,q['task'],q['target'],ocr_fn=ocr_one) for q in queries]
                return result,(time.perf_counter()-start)*1000
            def batch():
                start=time.perf_counter()
                result=propose_batch(image,queries,ocr_fn=ocr_batch)
                return result,(time.perf_counter()-start)*1000
            if round_no%2:
                together,batched_ms=batch()
                separately,oneshot_ms=one()
            else:
                separately,oneshot_ms=one()
                together,batched_ms=batch()
            for single,combined in zip(separately,together['proposals']):
                parity &= all(single[k]==combined[k] for k in
                              ('status','review_reasons','confidence','image_sha256',
                               'image','auto_click','model_evidence','text_packet_bytes'))
                for key in ('proposed','alternatives','confidence_scope'):
                    parity &= (single['review_packet'][key]==combined['review_packet'][key])
            one_times.append(oneshot_ms);batch_times.append(batched_ms)
        if not parity:
            raise AssertionError('Single and batched screenshot proposals diverged')
        if calls['one']!=96 or calls['batch']!=12:
            raise AssertionError('OCR observation count changed')
        report=dict(
            format='tavi-screenshot-batch-benchmark-v1',
            scope='12 paired synthetic-image tests, 8 targets each, scripted OCR callback; no real Windows OCR, host action, UI capture or LLM.',
            target_queries=96,
            one_shot_image_preparations=96,
            batched_image_preparations=12,
            one_shot_ocr_callbacks=calls['one'],
            batch_ocr_callbacks=calls['batch'],
            median_one_shot_ms=round(median(one_times),3),
            median_batched_ms=round(median(batch_times),3),
            median_speed_ratio=round(median(one_times)/median(batch_times),2),
            equal_proposal_decisions=True,
            hosted_calls=0,executed_actions=False,
            real_ocr_latency_measured=False,
            end_to_end_computer_use_speed_measured=False,
            note='The batch evaluates candidates on one immutable observation. It never permits blindly replaying the resulting proposals as a click sequence.')
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
