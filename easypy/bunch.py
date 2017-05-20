from easypy.exceptions import TException


class MissingRequiredKeys(TException):
    template = 'Bunch is missing required key(s) {_required}'


class KeyNotAllowed(TException):
    template = 'Bunch does not allow key(s) {_disallowed}'


class CannotDeleteRequiredKey(TException):
    template = 'Bunch cannot delete required key {_required}'


class Bunch(dict):

    __slots__ = ("__stop_recursing__",)
    KEYS = frozenset()  # if set, Bunch will ensure it consists of those keys, and those keys only

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verify_keys()

    def _verify_keys(self):
        if not self.KEYS:
            return
        missing = self.KEYS - set(self.keys())
        if missing:
            raise MissingRequiredKeys(_required=missing)
        disallowed = set(self.keys()) - self.KEYS
        if disallowed:
            raise KeyNotAllowed(_disallowed=disallowed)

    @classmethod
    def fromkeys(cls, *args):
        self = super().__new__(cls)
        self.update(dict.fromkeys(*args))
        self._verify_keys()
        return self

    def __delitem__(self, key):
        if key in self.KEYS:
            raise CannotDeleteRequiredKey(_required=key)
        super().__delitem__(key)

    def __setitem__(self, key, value):
        if key in self.KEYS:
            raise KeyNotAllowed(_disallowed=key)
        super().__setitem__(key, value)

    def pop(self, key, *args):
        if key in self.KEYS:
            raise CannotDeleteRequiredKey(_required=key)
        super().pop(key, *args)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            if name[0] == "_" and name[1:].isdigit():
                return self[name[1:]]
            raise AttributeError("%s has no attribute %r" % (self.__class__, name))

    def __getitem__(self, key):
        try:
            return super(Bunch, self).__getitem__(key)
        except KeyError:
            from numbers import Integral
            if isinstance(key, Integral):
                return self[str(key)]
            raise

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError("%s has no attribute %r" % (self.__class__, name))

    def __getstate__(self):
        return self

    def __setstate__(self, dict):
        self.update(dict)

    def __repr__(self):
        if getattr(self, "__stop_recursing__", False):
            items = sorted("%s" % k for k in self if isinstance(k, str) and not k.startswith("__"))
            attrs = ", ".join(items)
        else:
            dict.__setattr__(self, "__stop_recursing__", True)
            try:
                items = sorted("%s=%r" % (k, v) for k, v in self.items()
                               if isinstance(k, str) and not k.startswith("__"))
                attrs = ", ".join(items)
            finally:
                dict.__delattr__(self, "__stop_recursing__")
        return "%s(%s)" % (self.__class__.__name__, attrs)

    def _repr_pretty_(self, p, cycle):
        # used by IPython
        from easypy.colors import DARK_CYAN
        if cycle:
            p.text('Bunch(...)')
            return
        with p.group(6, 'Bunch(', ')'):
            for idx, (k, v) in enumerate(sorted(self.items())):
                if idx:
                    p.text(',')
                    p.breakable()
                with p.group(len(k)+1, DARK_CYAN(k) + "="):
                    p.pretty(self[k])

    def to_dict(self):
        return unbunchify(self)

    def to_json(self):
        import json
        return json.dumps(self.to_dict())

    def to_yaml(self):
        import yaml
        return yaml.dump(self.to_dict())

    def copy(self, deep=False):
        if deep:
            return _convert(self, self.__class__)
        else:
            return self.__class__(self)

    @classmethod
    def from_dict(cls, d):
        return _convert(d, cls)

    @classmethod
    def from_json(cls, d):
        import json
        return cls.from_dict(json.loads(d))

    @classmethod
    def from_yaml(cls, d):
        import yaml
        return cls.from_dict(yaml.load(d))

    def __dir__(self):
        members = set(k for k in self if isinstance(k, str) and (k[0] == "_" or k.replace("_", "").isalnum()))
        members.update(dict.__dir__(self))
        return sorted(members)

    def without(self, *keys):
        "Return a shallow copy of the bunch without the specified keys"
        return Bunch((k, v) for k, v in self.items() if k not in keys)

    def but_with(self, **kw):
        "Return a shallow copy of the bunch with the specified keys"
        return Bunch(self, **kw)


def _convert(d, typ):
    if isinstance(d, dict):
        return typ(dict((str(k), _convert(v, typ)) for k, v in d.items()))
    elif isinstance(d, (tuple, list, set)):
        return type(d)(_convert(e, typ) for e in  d)
    else:
        return d


def unbunchify(d):
    return _convert(d, dict)


def bunchify(d=None, **kw):
    d = _convert(d, Bunch) if d is not None else Bunch()
    if kw:
        d.update(bunchify(kw))
    return d


class _RigidBunchRequiredKeyRegistration(dict):
    def __init__(self):
        self._keys = set()

    def __getitem__(self, name):
        if name.startswith('_'):
            return super().__getitem__(name)
        else:
            self._keys.add(name)


class __RigidBunchMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        if bases:  # class the subclasses RigidBunch
            assert bases == (RigidBunch,)
            return _RigidBunchRequiredKeyRegistration()
        else:  # RigidBunch itself
            return {}

    def __new__(mcs, name, bases, classdict):
        if bases:  # class the subclasses RigidBunch
            assert bases == (RigidBunch,)
            return type.__new__(type, name, (Bunch,), dict(KEYS=frozenset(classdict._keys)))
        else:  # RigidBunch itself
            return type.__new__(mcs, name, bases, dict(classdict))


class RigidBunch(metaclass=__RigidBunchMeta):
    """
    A Bunch that can only contain certain keys, and must contain them all.

    Example:

        class RB(Bunch):
            a
            b
            c

        RB(a=1, b=2)  # will fail - `c` must be set
        RB(a=1, b=2, c=3, d=4)  # will fail - `d` is not allowed
        RB(a=1, b=2, c=3)  # will succeed - `a`, `b` and `c` are set
    """
