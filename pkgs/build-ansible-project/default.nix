{
  lib,
  runCommand,
  writeText,
  python3,
  fetchurl,
  fetchgit,
  purifier,
  tool,
  sdkVersion,
  gnutar,
  gzip,
  ...
}@scope:
{
  src,
  lockFile ? src + "/ansible-purifier.lock.json",
  playbook ? "playbook.yml",
  inventory ? "localhost,",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
  version ? "v0.1.0",
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; }
  );
  prepared = import ./environment.nix scope { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        "result"
        "__pycache__"
      ]);
  };
  project = runCommand "ansible-project" { nativeBuildInputs = [ tool ] ++ nativeBuildInputs; } ''
    cp -pr ${source} source
    chmod -R u+w source
    cd source
    export ANSIBLE_REMOTE_TEMP="$TMPDIR/remote"
    export ANSIBLE_HOME="$TMPDIR/ansible" ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=false
    export ANSIBLE_COLLECTIONS_PATH=${prepared.collections} ANSIBLE_PURIFIER_FROZEN=1
    if test -f ansible.cfg; then export ANSIBLE_CONFIG="$PWD/ansible.cfg"; else
      export ANSIBLE_CONFIG=${writeText "ansible.cfg" "[defaults]\n"}
    fi
    mkdir -p "$out"
    ansible-playbook -i ${lib.escapeShellArg inventory} ${lib.escapeShellArg playbook} > "$out/playbook.log"
    ${lib.optionalString doCheck checkCommand}
    cp -pr ${source} "$out/source"
  '';
  release =
    runCommand "ansible-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        test -e ${project}/playbook.log
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/ansible-project.tar.gz" -C ${source} .
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
