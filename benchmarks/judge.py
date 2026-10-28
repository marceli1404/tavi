"""Bounded pure-Python function judge. Not a general security sandbox."""
import ast
import builtins
import contextlib
import io
import json
import sys

ALLOWED_IMPORTS = {'typing','math','collections','itertools','functools','re'}
DENIED = {'open','exec','eval','compile','input','globals','locals','vars','getattr','setattr','delattr','breakpoint','help','exit','quit'}


def validate(source,allowed_imports=None):
    allowed_imports=ALLOWED_IMPORTS if allowed_imports is None else allowed_imports
    if len(source)>32_000:
        raise ValueError('Code exceeds32 KB')
    tree=ast.parse(source)
    nodes=list(ast.walk(tree))
    if len(nodes)>3000:
        raise ValueError('Code exceeds AST budget')
    for node in nodes:
        if isinstance(node,ast.Name) and (node.id.startswith('__') or node.id in DENIED):
            raise ValueError('Unsupported code name: '+node.id)
        if isinstance(node,ast.Attribute) and (node.attr.startswith('_') or node.attr in ('sys','os','modules','gi_frame','f_globals','f_locals')):
            raise ValueError('Unsupported code attribute: '+node.attr)
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            modules=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
            if any(m not in allowed_imports for m in modules) or getattr(node,'level',0):
                raise ValueError('Unsupported import')
    return tree


def guarded_import(name,globals=None,locals=None,fromlist=(),level=0):
    if name not in ALLOWED_IMPORTS|{'random','string'} or level:
        raise ImportError('Import not allowed')
    return builtins.__import__(name,globals,locals,fromlist,level)


def judge(code,test,entry_point):
    # Function candidates are statically restricted and execute only in this disposable worker.
    candidate=validate(code)
    checks=validate(test,ALLOWED_IMPORTS|{'random','string'})
    import random
    random.seed(0)
    safe_names='abs all any bool dict enumerate filter float frozenset int isinstance issubclass iter len list map max min next pow range reversed round set slice sorted str sum tuple zip Exception ValueError TypeError AssertionError StopIteration'.split()
    safe={name:getattr(builtins,name) for name in safe_names}
    safe['__import__']=guarded_import
    namespace={'__builtins__':safe}
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        exec(compile(candidate,'<candidate>','exec'),namespace)
        exec(compile(checks,'<upstream-tests>','exec'),namespace)
        namespace['check'](namespace[entry_point])
    return dict(passed=True,result='passed')


if __name__=='__main__':
    try:
        request=json.load(sys.stdin)
        print(json.dumps(judge(request['code'],request['test'],request['entry_point'])))
    except BaseException as error:
        print(json.dumps(dict(passed=False,result=type(error).__name__,detail=str(error)[:500])))
