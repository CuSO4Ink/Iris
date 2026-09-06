"""Exercise engine installation and project binding on disposable Git repositories."""
from __future__ import annotations

import difflib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'work/UEAgent'


def run(args: list[str], *, cwd: Path | None = None, succeeds: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    if succeeds and result.returncode:
        raise AssertionError(f'{args}\n{result.stdout}\n{result.stderr}')
    if not succeeds and not result.returncode:
        raise AssertionError(f'Expected rejection: {args}\n{result.stdout}')
    return result


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def init_repo(path: Path) -> None:
    run(['git', 'init', '-q', str(path)])
    run(['git', 'config', 'core.autocrlf', 'false'], cwd=path)
    run(['git', 'add', '.'], cwd=path)
    run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'Fixture source'], cwd=path)


def files(path: Path) -> dict[str, bytes]:
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob('*') if p.is_file() and '.git' not in p.parts}


def main() -> None:
    temp_root = ROOT / 'tmp/UEAgent'
    temp_root.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='engine-install-', dir=temp_root)).resolve()
    assert fixture.is_relative_to(temp_root.resolve())
    try:
        package = fixture / 'package'
        for name in ('install_engine.ps1', 'ueagent_common.ps1', 'bootstrap.ps1'):
            write(package / 'scripts' / name, (PACKAGE / 'scripts' / name).read_text(encoding='utf-8'))
        manifest = json.loads((PACKAGE / 'STACK-MANIFEST.json').read_text(encoding='utf-8'))
        write(package / 'STACK-MANIFEST.json', json.dumps(manifest))
        engine = fixture / 'Engine With Spaces'
        vibe = engine / manifest['runtime']['vibeue_engine_path']
        write(engine / '.gitignore', 'Engine/Plugins/AI/VibeUE/\n')
        build_version = {name: manifest['engine'][key] for name, key in (
            ('MajorVersion', 'major'), ('MinorVersion', 'minor'), ('PatchVersion', 'patch'), ('CompatibleChangelist', 'compatible_changelist'))}
        write(engine / 'Engine/Build/Build.version', json.dumps(build_version))
        descriptors = [
            'Engine/Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin',
            'Engine/Plugins/Experimental/Toolsets/EditorToolset/EditorToolset.uplugin',
            'Engine/Plugins/Experimental/PlatformCrypto/PlatformCrypto.uplugin',
            'Engine/Plugins/Experimental/Toolsets/NiagaraToolsets/NiagaraToolsets.uplugin',
            'Engine/Plugins/AI/VibeUE/VibeUE.uplugin',
        ]
        for relative in descriptors:
            write(engine / relative, json.dumps({'EnabledByDefault': False, 'Version': 1, 'VersionName': 'fixture', 'UserField': 'preserved'}))
        write(engine / 'Engine/Config/BaseEditorPerProjectUserSettings.ini',
              '[Unrelated]\nServerPortNumber=9123\nSentinel=keep\n\n[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]\nServerPortNumber=7000\nUserFlag=keep\n')
        write(engine / 'Engine/Config/BaseEditor.ini', '[Unrelated]\nEnabled=False\n\n[UEAgent.Reliable]\nEnabled=False\nUserFlag=keep\n')
        write(engine / 'Engine/Build/BatchFiles/Build.bat', '@echo off\r\necho %*>"%~dp0fixture-build.txt"\r\nexit /b 0\r\n')

        originals: dict[Path, str] = {}
        expected: dict[str, tuple[Path, str]] = {}
        original = '// first\n// second\nvoid Before();\n// fourth\n// fifth\n'
        composite = 'patches/niagara-mcp-authoring/vibeue/vibeue-ueagent-authoring.patch'
        refresh = 'patches/niagara-mcp-authoring/vibeue/vibeue-refresh-module-call-nodes.patch'
        relative_patches = list(dict.fromkeys(p for profile in manifest['profiles'].values() for p in profile['apply']))
        for index, relative in enumerate(relative_patches):
            is_vibe = relative.startswith('patches/vibeue-') or '/vibeue/' in relative
            repository = vibe if is_vibe else engine
            source_name = f'Source/VibeUE/Fixture/Patch{index}.cpp' if is_vibe else f'Engine/Source/Fixture/Patch{index}.cpp'
            before = original
            if relative in (composite, refresh):
                source_name = 'Source/VibeUE/Fixture/Authoring.cpp'
            if relative == refresh:
                before = original.replace('void Before();', 'void Before();\nvoid Authoring();')
            token = 'Authoring' if relative == composite else f'Patch{index}'
            after = before.replace('// fourth', f'void {token}();\n// fourth')
            source = repository / source_name
            originals.setdefault(source, original)
            expected[relative] = (source, after)
            patch = f'diff --git a/{source_name} b/{source_name}\n' + ''.join(difflib.unified_diff(
                before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f'a/{source_name}', tofile=f'b/{source_name}'))
            write(package / relative, patch)
        for source, content in originals.items():
            write(source, content)
        write(vibe / 'unrelated.txt', 'original\n')
        write(engine / 'unrelated.txt', 'original\n')
        init_repo(vibe)
        init_repo(engine)
        write(vibe / 'unrelated.txt', 'user edit in plugin\n')
        write(engine / 'unrelated.txt', 'user edit in engine\n')
        index_before = {repo: run(['git', 'ls-files', '--stage'], cwd=repo).stdout for repo in (engine, vibe)}
        installer = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'scripts/install_engine.ps1'), '-EngineRoot', str(engine), '-Profile', 'niagara-authoring']

        before = files(engine)
        run(installer + ['-CheckOnly'], succeeds=False)
        assert files(engine) == before, 'CheckOnly changed an uninstalled checkout'
        conflict_source = expected[manifest['profiles']['niagara-authoring']['apply'][-1]][0]
        write(conflict_source, 'conflicting local source edit\n')
        before = files(engine)
        run(installer + ['-SkipBuild'], succeeds=False)
        assert files(engine) == before, 'A conflicting plugin patch allowed partial engine writes'
        write(conflict_source, originals[conflict_source])

        installed = json.loads(run(installer).stdout)
        assert installed['built'] and not installed['liveVerified']
        assert 'UnrealEditor Win64 Development' in (engine / 'Engine/Build/BatchFiles/fixture-build.txt').read_text()
        for relative in manifest['profiles']['default']['apply'] + manifest['profiles']['niagara-authoring']['apply']:
            if relative == composite:
                continue  # The refresh patch advances the same source further.
            source, content = expected[relative]
            assert source.read_text() == content, f'Manifest patch was skipped: {relative}'
        for relative in descriptors:
            descriptor = json.loads((engine / relative).read_text())
            # Crypto is no longer an executor dependency; unrelated plugin defaults stay untouched.
            assert descriptor['EnabledByDefault'] == ('PlatformCrypto' not in relative)
            assert descriptor['UserField'] == 'preserved'
        mcp_ini = (engine / 'Engine/Config/BaseEditorPerProjectUserSettings.ini').read_text()
        reliable_ini = (engine / 'Engine/Config/BaseEditor.ini').read_text()
        assert '[Unrelated]\nServerPortNumber=9123' in mcp_ini and 'ServerPortNumber=8000' in mcp_ini and 'UserFlag=keep' in mcp_ini
        assert '[Unrelated]\nEnabled=False' in reliable_ini and '[UEAgent.Reliable]\nEnabled=True' in reliable_ini and 'UserFlag=keep' in reliable_ini
        before = files(engine)
        assert json.loads(run(installer + ['-CheckOnly']).stdout)['sourceAndDefaultsVerified']
        assert not json.loads(run(installer + ['-SkipBuild']).stdout)['built']
        assert files(engine) == before, 'Repeat installation changed already-installed source/defaults'
        extended = json.loads(run(installer + ['-EngineExtensions', '-SkipBuild']).stdout)
        assert 'engine-extensions' in extended['profiles']
        source, content = expected[manifest['profiles']['engine-extensions']['apply'][0]]
        assert source.read_text() == content
        run(installer + ['-EngineExtensions', '-CheckOnly'])

        project = fixture / 'Consumer Project'
        uproject = project / 'Consumer.uproject'
        write(uproject, json.dumps({'FileVersion': 3, 'Plugins': [{'Name': 'UserPlugin', 'Enabled': True}]}))
        write(project / '.mcp.json', json.dumps({'mcpServers': {'user-server': {'url': 'http://localhost:9999/'}}}))
        project_before = uproject.read_bytes()
        bootstrap = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'scripts/bootstrap.ps1'), '-UProject', str(uproject), '-EngineRoot', str(engine), '-Profile', 'niagara-authoring']
        run(bootstrap)
        run(bootstrap + ['-CheckOnly'])
        assert uproject.read_bytes() == project_before
        assert 'user-server' in json.loads((project / '.mcp.json').read_text())['mcpServers']
        route = json.loads((project / 'Saved/UEAgent/route.json').read_text())
        assert route['engineRoot'] == str(engine) and route['profile'] == 'niagara-authoring'
        binding_before = {name: (project / name).read_bytes() for name in ('.mcp.json', 'Saved/UEAgent/route.json')}
        write(project / 'Plugins/VibeUE/VibeUE.uplugin', json.dumps({'FileVersion': 3}))
        shadow = run(bootstrap, succeeds=False)
        assert 'shadows the engine installation' in shadow.stderr
        assert all((project / name).read_bytes() == data for name, data in binding_before.items())
        for repo, index in index_before.items():
            assert run(['git', 'ls-files', '--stage'], cwd=repo).stdout == index
        assert (vibe / 'unrelated.txt').read_text() == 'user edit in plugin\n'
        assert (engine / 'unrelated.txt').read_text() == 'user edit in engine\n'
        print(json.dumps({'passed': True, 'checks': ['check_only_no_writes', 'conflict_preserves_both_repositories', 'manifest_order_including_refresh', 'scoped_ini_updates', 'plugin_defaults', 'build_dispatch', 'repeat_installation', 'additive_engine_extensions', 'consumer_bootstrap', 'project_plugin_shadow_rejected', 'dirty_work_and_index_preserved'], 'realUnrealBuilt': False}))
    finally:
        assert fixture.is_relative_to(temp_root.resolve())
        if sys.exc_info()[0]:
            print(f'Failure artifacts: {fixture}', file=sys.stderr)
        else:
            def remove_readonly(function, path, _error):
                assert Path(path).resolve().is_relative_to(fixture)
                Path(path).chmod(stat.S_IWRITE)
                function(path)
            shutil.rmtree(fixture, onexc=remove_readonly)


if __name__ == '__main__':
    main()
