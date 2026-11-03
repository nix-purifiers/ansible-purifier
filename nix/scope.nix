{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.python3.withPackages (ps: [ ps.ansible-core ]);
  core = pkgs.python3.pkgs.ansible-core.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      ${pkgs.python3}/bin/python3 ${../native/patch-native.py}
    '';
  });
  tool = pkgs.python3.withPackages (_: [ scope.core ]);
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      core = toString pkgs.python3.pkgs.ansible-core.src;
      patch = builtins.hashFile "sha256" ../native/patch-native.py;
    }
  );
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildAnsibleProject = scope.callPackage ./build-project.nix { };
})
