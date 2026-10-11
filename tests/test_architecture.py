"""Enforce import ownership and prohibit file IO outside the repository."""
import ast
from outdoorwise.config import ROOT
ALLOWED={
 'modules':{'contracts'}, 'storage':{'contracts'},
 'pipeline':{'contracts'}, 'contracts':{'contracts'},
 'agent':{'contracts','agent'}, 'collectors':{'contracts'}, 'services':{'contracts'},
}
def test_dependency_direction():
    for package,allowed in ALLOWED.items():
        for path in (ROOT/'outdoorwise'/package).glob('*.py'):
            tree=ast.parse(path.read_text())
            for n in ast.walk(tree):
                names=[]
                if isinstance(n,ast.Import): names=[a.name for a in n.names]
                elif isinstance(n,ast.ImportFrom):
                    if n.level: continue
                    names=[n.module or '']
                for name in names:
                    if name.startswith('outdoorwise.'):
                        target=name.split('.')[1]
                        assert target in allowed, f'{path.name} illegally imports {name}'
                if package in {'modules','agent'} and isinstance(n,ast.Call):
                    func=n.func
                    name=func.id if isinstance(func,ast.Name) else func.attr if isinstance(func,ast.Attribute) else ''
                    assert name not in {'open','read_text','read_bytes','write_text','write_bytes'}, f'File IO in {path}'
