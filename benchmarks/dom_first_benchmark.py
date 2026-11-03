"""Paired DOM-first vs always-OCR computer-use observation benchmark.

Synthetic host control data, one generated screenshot and scripted OCR;
NOT a native browser or Windows OCR benchmark. No actions or hosted LLM.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
import sys
import time

from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tavi_observe import dispatch
from tavi_compact import propose_batch


def main():
    with TemporaryDirectory() as folder:
        image=Path(folder)/'current-screen.png'
        im=Image.new('RGB',(1280,720),'white')
        draw=ImageDraw.Draw(im)
        words=[]
        queries=[]
        controls=[]
        for i in range(16):
            label=f'Button{i}'
            x=40+(i%4)*300
            y=45+(i//4)*150
            draw.rectangle((x,y,x+220,y+65),fill='#222222')
            words.append(dict(text=label,x=x+25,y=y+15,width=110,height=32))
            queries.append(dict(id=f'q{i}',task='Inspect '+label,
                                target=label,role='button'))
            # 12 controls are structurally present; four require OCR.
            if i<12:
                controls.append(dict(id=f'host-control-{i}',label=label,role='button',
                                     context='Main',visible=True,enabled=True,
                                     bounds=[x,y,220,65]))
        im.save(image)
        im.close()

        ocr_counts=dict(always=0,dom_first=0,all_dom=0)
        def make_ocr(kind):
            def ocr(_):
                ocr_counts[kind]+=1
                return dict(status='available',words=list(words))
            return ocr

        always_times=[]
        mixed_times=[]
        all_dom_times=[]
        parity=True
        rounds=12
        for n in range(rounds):
            snap=dict(format='tavi-control-snapshot-v1',snapshot_id=f'observation-{n}',
                      captured_at=datetime.now(timezone.utc).isoformat(),
                      source='supported_browser_dom',viewport=[1280,720],controls=controls)
            binding=dict(path=str(image),snapshot_id=snap['snapshot_id'])

            def always():
                start=time.perf_counter()
                result=propose_batch(image,[dict(id=q['id'],task=q['task'],target=q['target'])
                                            for q in queries],ocr_fn=make_ocr('always'))
                return result,(time.perf_counter()-start)*1000

            def mixed():
                start=time.perf_counter()
                result=dispatch(snap,queries,image=binding,ocr_fn=make_ocr('dom_first'))
                return result,(time.perf_counter()-start)*1000

            def exact():
                all_controls=list(controls)+[
                    dict(id=f'host-control-{i}',label=f'Button{i}',role='button',
                         context='Main',visible=True,enabled=True,
                         bounds=[40+(i%4)*300,45+(i//4)*150,220,65])
                    for i in range(12,16)]
                full=dict(snap,controls=all_controls)
                start=time.perf_counter()
                result=dispatch(full,queries,image=binding,ocr_fn=make_ocr('all_dom'))
                return result,(time.perf_counter()-start)*1000

            if n%2:
                selective,selective_ms=mixed()
                baseline,baseline_ms=always()
            else:
                baseline,baseline_ms=always()
                selective,selective_ms=mixed()
            no_image,fast_ms=exact()

            parity &= selective['counts']['exact_host_controls']==12
            parity &= selective['counts']['visual_review']==4
            parity &= selective['counts']['ocr_passes']==1
            parity &= no_image['counts']['exact_host_controls']==16
            parity &= no_image['counts']['ocr_passes']==0
            parity &= all(no_image['routes'][i]['route']=='host_control' for i in range(16))
            for i in range(12,16):
                visual=selective['routes'][i]['visual']
                single=baseline['proposals'][i]
                parity &= visual['status']==single['status']
                parity &= visual['proposed']==single['review_packet']['proposed']
                parity &= visual['review_reasons']==single['review_reasons']
            always_times.append(baseline_ms)
            mixed_times.append(selective_ms)
            all_dom_times.append(fast_ms)

        assert parity, 'DOM-first escalation changed matching proposal decisions'
        assert ocr_counts==dict(always=12,dom_first=12,all_dom=0)
        report=dict(
            format='tavi-dom-first-benchmark-v1',
            scope='12 paired synthetic snapshots, 16 queries each; 12 DOM matches and 4 missing. Scripted OCR only, no real browser/Windows OCR, capture, click or model call.',
            rounds=rounds,
            controls_per_snapshot=16,
            dom_exact_per_snapshot=12,
            ocr_escalations_per_snapshot=4,
            always_ocr_preparations=rounds,
            dom_first_preparations=rounds,
            all_dom_image_preparations=0,
            always_ocr_passes=ocr_counts['always'],
            selective_ocr_passes=ocr_counts['dom_first'],
            all_dom_ocr_passes=ocr_counts['all_dom'],
            median_always_image_processing_ms=round(median(always_times),3),
            median_dom_first_mixed_ms=round(median(mixed_times),3),
            median_all_dom_no_image_ms=round(median(all_dom_times),3),
            mixed_speed_ratio=round(median(always_times)/median(mixed_times),2),
            all_dom_speed_ratio=round(median(always_times)/median(all_dom_times),2),
            matching_visual_evidence=True,
            executed_actions=False,hosted_calls=0,
            end_to_end_speed_measured=False,actual_model_tokens_measured=False)
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
