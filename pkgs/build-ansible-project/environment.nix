{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  tool,
  sdkVersion,
  ...
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  tree = purifier.tree (
    {
      name = "ansible-locked-artifacts";
      entries = checked.entries;
      inherit
        runCommand
        fetchurl
        fetchgit
        writeText
        python3
        ;
    }
    // fetchers
  );
  artifacts = map (e: "${tree}/${e.path}") checked.entries;
  collections = runCommand "ansible-native-collections" { nativeBuildInputs = [ tool ]; } ''
    export ANSIBLE_HOME="$TMPDIR/ansible" ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=false
    export ANSIBLE_COLLECTIONS_PATH="$out"
    mkdir -p "$out/ansible_collections"
    ${lib.optionalString (artifacts != [ ]) ''
      ansible-galaxy collection install --offline -p "$out" ${lib.escapeShellArgs artifacts}
    ''}
  '';
  manifest = writeText "ansible-environment.json" (
    builtins.toJSON {
      inherit tree collections;
      sdk = sdkVersion;
    }
  );
  output = runCommand "ansible-locked-environment" { passthru = { inherit collections; }; } ''
    mkdir -p "$out"
    ln -s ${manifest} "$out/manifest.json"
  '';
in
assert lib.assertMsg (checked.data.sdk == sdkVersion) "Ansible SDK changed; update the lock";
{
  inherit output tree collections;
}
