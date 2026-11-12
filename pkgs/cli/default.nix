{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  cacert,
  original,
  tool,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "ansible-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/ansible-purifier"
    cp -r ansible_purifier pkgs lib-overlays native "$out/lib/ansible-purifier/"
    install -m755 bin/ansible-purifier "$out/bin/ansible-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/ansible-purifier/pkgs/build-ansible-project/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/ansible-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default ANSIBLE_PURIFIER_GH ${gh}/bin/gh \
      --set ANSIBLE_PURIFIER_ORIGINAL ${original} \
      --set ANSIBLE_PURIFIER_TOOL ${tool} \
      --set ANSIBLE_PURIFIER_PYTHON ${original}/bin/python \
      --set ANSIBLE_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set ANSIBLE_PURIFIER_SDK "$out"
    for program in ${tool}/bin/ansible*; do
      name=$(basename "$program")
      makeWrapper "$out/bin/ansible-purifier" "$out/bin/$name" --add-flags "--native=$name"
    done
  '';
  meta = {
    description = "Native Ansible with locked Nix-resolved Galaxy collections";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "ansible-purifier";
  };
}
