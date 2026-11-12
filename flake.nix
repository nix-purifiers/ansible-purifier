{
  description = "Locked, Nix-resolved Galaxy collections for Ansible";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        ansible-purifier = import ./pkgs/default.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).ansible-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ansible-purifier";
          meta.description = "Lock native Ansible resources";
        };
      });
      lib.ansible-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default)).ansible-purifier;
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.ansible-purifier.buildAnsibleProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = ''grep -q '42.0' "$out/playbook.log"'';
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
