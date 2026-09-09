#!/usr/bin/env python3
"""Offline, operator-directed Android capture for design TC requests."""
import argparse,json,shutil,subprocess,datetime,re
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description='TC대로 화면을 준비한 뒤 현재 화면만 촬영합니다.')
    p.add_argument('queue',nargs='?',default='촬영요청.json');p.add_argument('--case');p.add_argument('--adb');p.add_argument('--serial')
    args=p.parse_args();q=json.loads(Path(args.queue).read_text())
    if q.get('format')!='design-capture-request-v1' or q.get('platform')!='android':p.error('Android 촬영 요청 파일이 필요합니다.')
    adb=args.adb or shutil.which('adb') or str(Path.home()/'Library/Android/sdk/platform-tools/adb')
    devices=subprocess.run([adb,'devices'],capture_output=True,text=True,check=True).stdout
    ids=[line.split()[0] for line in devices.splitlines()[1:] if line.endswith('\tdevice')]
    serial=args.serial
    if serial and serial not in ids:p.error('지정한 기기가 연결되지 않았습니다.')
    if not serial:
        if len(ids)!=1:p.error('연결된 기기 하나가 필요합니다. 여러 대이면 --serial로 선택하세요.')
        serial=ids[0]
    cases=[r for r in q['cases'] if not args.case or r['case_id']==args.case]
    if not cases:p.error('촬영할 TC가 없습니다.')
    out=Path('shots')/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');out.mkdir(parents=True)
    results=[]
    for r in cases:
        if not re.fullmatch('[a-f0-9]{32}',r['case_id']):p.error('TC 식별자가 잘못되었습니다.')
        print('\n',r['seq'],r['design_name'],'\n준비:',r['prerequisite'],'\n절차:\n',r['steps'],'\n기대 모습:',r['expected'])
        if input('기기에서 위 상태를 만든 뒤 Enter로 촬영 (s=건너뜀): ').lower()=='s':continue
        result=subprocess.run([adb,'-s',serial,'exec-out','screencap','-p'],capture_output=True,check=True,timeout=30)
        if not result.stdout.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('PNG 촬영에 실패했습니다.')
        filename='TC-'+r['case_id']+'@capture.png';(out/filename).write_bytes(result.stdout)
        results.append({'case_id':r['case_id'],'파일':filename,'화면이름':r['design_name']})
        (out/'찍은목록.json').write_text(json.dumps({'format':'design-capture-results-v1','plan_id':q['plan_id'],'찍힌것':results},ensure_ascii=False,indent=2))
        print('저장:',out/filename)
    print('포털 추가 촬영 대기의 결과 가져오기에 이 폴더의 PNG와 찍은목록.json을 선택하세요:',out)
if __name__=='__main__':main()
