

class SteamIDException(Exception):
    def __init__(self, *args):
        super().__init__(args)


class InvalidCommunityIDException(SteamIDException):
    def __init__(self, *args):
        super().__init__(args)


class InvalidSteamID1Exception(SteamIDException):
    def __init__(self, *args):
        super().__init__(args)


class InvalidSteamID3Exception(SteamIDException):
    def __init__(self, *args):
        super().__init__(args)


class SteamID:
    # Derived from https://gist.github.com/bcahue/4eae86ae1d10364bb66d
    _sid64_base: int = 76561197960265728
    steam_id_1: str = None
    steam_id_3: str = None
    steam_id_64: int = None
    _input: str = None

    @classmethod
    def _sid64_to_sid1(cls, sid64: int | str) -> str:
        if isinstance(sid64, str):
            try:
                _comm_id = int(sid64)
            except ValueError:
                raise InvalidCommunityIDException(f"Community ID of '{sid64}' is not a valid community ID.")
        else:
            _comm_id = sid64

        steam_id_acct = _comm_id - cls._sid64_base
        return f"STEAM_0:{0 if steam_id_acct % 2 == 0 else 1}:{steam_id_acct // 2}"

    @classmethod
    def _sid1_to_sid64(cls, sid1: str) -> int:
        _sid1_components = sid1.split(":")
        try:
            _comm_id = int(_sid1_components[-1])*2
        except ValueError:
            raise InvalidSteamID1Exception(f"SteamID1 of '{sid1}' is not a valid SteamID1. "
                                           f"The last component must parse as an int.")

        if _sid1_components[1] == '1':
            _comm_id += 1

        return _comm_id + cls._sid64_base

    @classmethod
    def _sid1_to_sid3(cls, sid1: str) -> str:
        _sid1_components = sid1.split(":")
        try:
            _component_1 = int(_sid1_components[1])
            _component_2 = int(_sid1_components[2])
        except ValueError:
            raise InvalidSteamID1Exception(f"SteamID1 of '{sid1}' is not a valid SteamID1. "
                                           f"The middle and last components must parse as ints.")

        return f"[U:1:{_component_2 * 2 + _component_1}]"

    @classmethod
    def _sid64_to_sid3(cls, sid64: int | str) -> str:
        if isinstance(sid64, str):
            try:
                _comm_id = int(sid64)
            except ValueError:
                raise InvalidCommunityIDException(f"Community ID of '{sid64}' is not a valid community ID.")
        else:
            _comm_id = sid64

        return f"[U:1:{_comm_id - cls._sid64_base}]"

    @classmethod
    def _sid3_to_sid1(cls, sid3: str) -> str:
        _sid3 = sid3.replace("[", "").replace("]", "")

        try:
            _comm_id = int(_sid3.split(":")[-1])
        except ValueError:
            raise InvalidSteamID3Exception(f"SteamID13 of '{sid3}' is not a valid SteamID3. "
                                           f"The last component must parse as an int.")

        return f"STEAM_0:{0 if _comm_id % 2 == 0 else 1}:{_comm_id // 2}"

    @classmethod
    def _sid3_to_sid64(cls, sid3: str) -> int:
        _sid3 = sid3.replace("[", "").replace("]", "")

        try:
            _comm_id = int(_sid3.split(":")[-1])
        except ValueError:
            raise InvalidSteamID3Exception(f"SteamID13 of '{sid3}' is not a valid SteamID3. "
                                           f"The last component must parse as an int.")

        return _comm_id + cls._sid64_base

    def _populate_other_fields(self) -> None:
        if self.steam_id_1 is not None:
            self.steam_id_3 = self._sid1_to_sid3(self.steam_id_1)
            self.steam_id_64 = self._sid1_to_sid64(self.steam_id_1)
        elif self.steam_id_3 is not None:
            self.steam_id_1 = self._sid3_to_sid1(self.steam_id_3)
            self.steam_id_64 = self._sid3_to_sid64(self.steam_id_3)
        elif self.steam_id_64 is not None:
            self.steam_id_1 = self._sid64_to_sid1(self.steam_id_64)
            self.steam_id_3 = self._sid64_to_sid3(self.steam_id_64)
        else:
            raise ValueError(f"No identifiable/convertable steam ID was found")

    def __init__(self, steam_id_str: str) -> None:
        self._input = steam_id_str

        if steam_id_str.startswith("STEAM_0"):
            self.steam_id_1 = steam_id_str
        elif steam_id_str.startswith("765611"):
            self.steam_id_64 = int(steam_id_str)
        elif steam_id_str.startswith("[U:1:"):
            self.steam_id_3 = steam_id_str
        else:
            raise SteamIDException(f"Could not identify what type of SteamID this is: '{steam_id_str}' - if its the "
                                   f"variable component of a SteamID3, place it inside a [U:1:<var>].")
        self._populate_other_fields()

    def get_profile_link(self):
        return f"https://steamcommunity.com/profiles/{self.steam_id_64}"

    def get_steam_history(self):
        return f"https://steamhistory.net/id/{self.steam_id_64}"

    def __repr__(self) -> str:
        return (f"@[Py-SteamID SteamID64: {self.steam_id_64:19} "
                f"SteamID3: {self.steam_id_3:19} SteamID1: {self.steam_id_1:19}]")

    def __eq__(self, other) -> bool:
        if isinstance(other, SteamID):
            return self.steam_id_64 == other.steam_id_64
        else:
            raise ValueError(f"Cannot compare SteamID and {type(other)}.")


if __name__ == "__main__":
    # killjoy [https://steamhistory.net/id/76561198144228983]
    _kj_sid1 = "STEAM_0:1:91981627"
    _test_sid1 = SteamID(_kj_sid1)
    _title = "Killjoy steamID"
    print(f"{_title:18}: {_kj_sid1:18} --> {_test_sid1}")

    # duckDecoy [https://steamhistory.net/id/76561197972854064]
    _duckdecoy_sid64 = "76561197972854064"
    _test_sid2 = SteamID(_duckdecoy_sid64)
    _title = "duckDecoy steamID"
    print(f"{_title:18}: {_duckdecoy_sid64:18} --> {_test_sid2}")

    # Killfish [https://steamhistory.net/id/76561197996862168]
    _killfish_sid3 = "[U:1:36596440]"
    _test_sid3 = SteamID(_killfish_sid3)
    _title = "Killfish steamID"
    print(f"{_title:18}: {_killfish_sid3:18} --> {_test_sid3}")
