{ lib }:
{
  src,
  lockFile ? src + "/ansible-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s))
    && builtins.match ".*[\n\r].*" s == null;
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "ansible"
    && builtins.isString (data.sdk or null)
    && relative (data.requirements or null)
    && builtins.isAttrs (data.inputs or null)
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && builtins.isAttrs (e.ansible or null)
      && builtins.isString (e.ansible.name or null)
      && builtins.match "[A-Za-z0-9_]+[.][A-Za-z0-9_]+" e.ansible.name != null
      && builtins.isString (e.ansible.version or null)
      && e.path == "artifacts/${e.ansible.name}.tar.gz"
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://galaxy.ansible.com/" e.url
      && !(lib.hasInfix "?" e.url)
      && !(lib.hasInfix "#" e.url)
      && (e.mirrors or null) == [ ]
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
    ) entries;
  valid =
    shape
    && builtins.length (lib.unique (map (e: e.ansible.name) entries)) == builtins.length entries
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          [ data.requirements ]
          ++ data.extraInputs
          ++ lib.optional (builtins.pathExists (src + "/ansible.cfg")) "ansible.cfg"
        )
      )
    && builtins.all (
      name:
      relative name
      && builtins.pathExists (src + "/${name}")
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
    ) (builtins.attrNames data.inputs);
in
{
  purifier = "ansible";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Ansible lock is missing, malformed, or stale; run ansible-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
