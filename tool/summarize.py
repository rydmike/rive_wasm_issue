#!/usr/bin/env python3
"""Validate completed captures and summarize observed results without assuming failures."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'evidence'
summary = []
for variant in ['newest','fixed','stable','a-only','b-only']:
    for compiler in ['wasm','js']:
        name=variant+'-'+compiler
        file=root/(name+'.json')
        if not file.exists():
            continue
        d=json.loads(file.read_text())
        logs=[x['text'] for x in d['console']]
        assert d.get('complete'), (name,d.get('error'))
        assert not d['pageErrors'], (name,d['pageErrors'])
        assert d['environment']['crossOriginIsolated'], name
        assert not any('[repro] FATAL' in x for x in logs), name
        passed=[x for x in logs if x.startswith('[repro] PASS ')]
        failed=[x for x in logs if x.startswith('[repro] FAIL ')]
        assert len(passed)+len(failed)==30, (name,len(passed),len(failed))
        for line in passed:
            if 'number(Coin/Item_Value)' in line:
                assert line.endswith(': 1300') or line.endswith(': 1300.0'),(name,line)
            elif 'enumerator(Item_Selection/Item_Selection)' in line:
                assert line.endswith(': Gem'),(name,line)
            elif 'file.enums' in line:
                assert line.endswith('Item_Selection=[Coin, Gem]'),(name,line)
        wasm=compiler=='wasm'
        actual='dart2wasm' if wasm else 'dart2js'
        assert any('compiler='+actual in x for x in logs),name
        requested=[x for x in d['requests'] if '/main.dart.' in x]
        assert any(x.endswith('main.dart.wasm' if wasm else 'main.dart.js') for x in requested),name
        if wasm:
            assert not any(x.endswith('main.dart.js') for x in requested),name
        growth=[g for g in d['environment']['memoryGrowth'] if 'flutter-native-wasm@' in g.get('stack','')]
        assert growth and all(g['detached'] and g['after']>g['before'] for g in growth),name
        assert any('[repro] PASS before number' in x for x in logs),name
        responses=[r for r in d['responses'] if r['url']==d['url']+'/']
        assert responses,name
        assert responses[0]['headers']['cross-origin-opener-policy']=='same-origin'
        assert responses[0]['headers']['cross-origin-embedder-policy']=='credentialless'
        enum_failed=[x for x in failed if 'file.enums' in x]
        path_failed=[x for x in failed if 'number(' in x or 'enumerator(' in x]
        row={'case':name,'compiler':actual,'pass':len(passed),'fail':len(failed),
             'enum_failures':len(enum_failed),'path_failures':len(path_failed),
             'crossOriginIsolated':True,'capturedAt':d['capturedAt'],'browser':d['browser'],
             'growth':[{k:g[k] for k in ['before','after','delta','detached']} for g in growth],
             'app_requests':requested,'failures':failed}
        summary.append(row)
        print(f"{name}: {len(passed)} PASS, {len(failed)} FAIL; enums={len(enum_failed)}, paths={len(path_failed)}; {actual}; real Rive heap growth")
(root/'matrix.json').write_text(json.dumps(summary,indent=2)+'\n')
print(f'Validated {len(summary)} captured cases; no expected failure counts were imposed.')
