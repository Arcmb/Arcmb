from pathlib import Path

p=Path(__file__).resolve().parent/'verify_model_data.py'
s=p.read_text(encoding='utf-8')
lines=s.splitlines()
needles=('create_user','role','mapping','Verificação','verificacao','special','especial','coordenador','master','preview','confirm')
print('VERIFY_MODEL_SOURCE_BEGIN',flush=True)
printed=set()
for i,line in enumerate(lines):
    if any(n.lower() in line.lower() for n in needles):
        a=max(0,i-4); b=min(len(lines),i+7)
        if any(x<=i<y for x,y in printed):
            continue
        printed.add((a,b))
        print(f'VERIFY_MODEL_LINES {a+1}-{b}',flush=True)
        for j in range(a,b):
            print(f'{j+1:04d}: {lines[j]}',flush=True)
print('VERIFY_MODEL_SOURCE_END',flush=True)
