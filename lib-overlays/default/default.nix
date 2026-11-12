final: prev: {
  ansible-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
