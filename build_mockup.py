"""Build the standalone C3 local preview from C3-owned data and assets only."""
from pathlib import Path
from datetime import date
import json,shutil
ROOT=Path(__file__).resolve().parent
DEST=ROOT/'maquette/dist'

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    source=ROOT/'data/current.json'
    if not source.exists():source=ROOT/'data/history_20261025.json'
    data=json.loads(source.read_text(encoding='utf8'))
    (DEST/'data.js').write_text('window.C3_DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf8')
    shutil.copyfile(ROOT/'assets/chart.min.js',DEST/'chart.min.js')
    for name in ('index.html','style.css','app.js'):shutil.copyfile(ROOT/'maquette'/name,DEST/name)
    html=(DEST/'index.html').read_text(encoding='utf8')
    end=date.fromisoformat(data['end']);last=end.day;n=len(data['dates'])
    months=['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
    label=f'{last} {months[end.month-1]} {end.year}'
    period=f'1–{last} octobre 2026' if end.month==10 else f'1er octobre – {label}'
    html=html.replace('1–25 octobre 2026',period).replace('le 25 octobre.',f'le {label}.').replace('données arrêtées au 25 octobre 2026',f'données arrêtées au {label}').replace('Historique des prix régionaux TTC du 1er au 25 octobre',f'Historique des prix régionaux TTC du 1er octobre au {label}').replace('25 journées',f'{n} journées').replace('25 OCT.',f'{last} {months[end.month-1][:3].upper()}.').replace('2026-10-25',data['end']).replace('max="24" value="24"',f'max="{n-1}" value="{n-1}"')
    html=html.replace('Historiques publiés de C1 et C2','Historiques publiés')
    (DEST/'index.html').write_text(html,encoding='utf8')
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(DEST/'style.css').read_text(encoding='utf8')+'</style>')
    for name in ('chart.min.js','data.js','app.js'):
        script=(DEST/name).read_text(encoding='utf8').replace('</script','<\\/script')
        html=html.replace(f'<script src="{name}"></script>','<script>'+script+'</script>')
    for target in (ROOT/'maquette/C3.html',DEST/'C3.html'):target.write_text(html,encoding='utf8')
    print(f'C3 local preview: {n} days, through {data["end"]}; no deployment')

if __name__=='__main__':main()
