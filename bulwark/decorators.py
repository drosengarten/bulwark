"""Generates decorators for each check in `checks.py`."""
import functools
import sys
from inspect import Parameter, getfullargspec, getmembers, isfunction, signature

import bulwark.checks as ck
from bulwark.generic import snake_to_camel


class BaseDecorator(object):
    df_allowed_types = (int, str, type(None))

    def __init__(self, *args, **kwargs):
        self.enabled = kwargs.pop("enabled", True)  # setter to enforce bool would be a lot safer
        # self.warn = False ? No - put at func level for all funcs and pass through
        self.params = getfullargspec(self.check_func).args[1:]

        self.__dict__.update(dict(zip(self.params, args)))
        self.__dict__.update(**kwargs)

        if type(self._df) not in self.df_allowed_types:
            msg = ("'df' arg cannot by of type {}.\n"
                   "Only allowed types are:\n"
                   " str:  arg name of the input argument to the decorated function to check\n"
                   " int:  the entry in a tuple returned by the decorated function to check\n"
                   " None: check the single dataframe return by the decorated function".format(type(self._df))
                   )
            raise TypeError(msg)

    @property
    def _df(self):
        return self.__dict__.get('df', None)

    def __call__(self, f):

        if type(self._df) is str:
            if not self._has_arg_name(self._df, f):
                raise NameError("'{}' is not an arg to function '{}'".format(self._df, f.__name__))

        @functools.wraps(f)
        def decorated(*args, **kwargs):

            if not self.enabled:
                return f(*args, **kwargs)

            check_kwargs = {k: v for k, v in self.__dict__.items()
                            if k not in ["check_func", "enabled", "params"]}

            if self._df is None:
                res = f(*args, **kwargs)
                check_kwargs['df'] = res
                self.check_func(**check_kwargs)
                return res

            if type(self._df) is int:
                res = f(*args, **kwargs)
                if type(res) is not tuple:
                    raise TypeError('Your function needs to return a tuple to use df=<int> in this decorator')
                check_kwargs['df'] = res[self._df]
                self.check_func(**check_kwargs)
                return res

            if type(self._df) is str:
                df_default = self._get_arg_default(f, self._df)
                df_value = self._get_arg_value(f, self._df, *args, **kwargs)
                if isinstance(df_default, Parameter.empty) or (df_value is not None):
                    check_kwargs['df'] = df_value
                    self.check_func(**check_kwargs)
                res = f(*args, **kwargs)
                return res
        return decorated

    @staticmethod
    def _has_arg_name(arg_name, func):
        sig = signature(func)
        res = arg_name in sig.parameters
        return res

    @staticmethod
    def _get_arg_default(func, arg_name):
        func_sig = signature(func)
        res = func_sig.parameters[arg_name].default
        return res

    @staticmethod
    def _get_arg_value(func, arg_name, *args, **kwargs):
        func_sig = signature(func)
        bound_args = func_sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        res = bound_args.arguments[arg_name]
        return res


def decorator_factory(decorator_name, func):
    """Takes in a function and outputs a class that can be used as a decorator."""
    class decorator_name(BaseDecorator):
        check_func = staticmethod(func)

    return decorator_name


# Automatically creates decorators for each function in bulwark.checks
this_module = sys.modules[__name__]
check_functions = [func[1]
                   for func in getmembers(ck, isfunction)
                   if func[1].__module__ == 'bulwark.checks']

for func in check_functions:
    decorator_name = snake_to_camel(func.__name__)
    setattr(this_module, decorator_name, decorator_factory(decorator_name, func))


class CustomCheck:
    """
    Notes:
        - This code is purposefully located below the auto-generation of decorators,
          so this overwrites the auto-generated CustomCheck.
        - `CustomCheck`'s __init__ and __call__ diverge from `BaseDecorator`,
          since the check_func needs to be set by the user at creation time.

    TODO: Work this into BaseDecorator?

    """

    def __init__(self, *args, **kwargs):
        self.enabled = kwargs.pop("enabled", True)  # setter to enforce bool would be a lot safer
        # self.warn = False ? No - put at func level for all funcs and pass through

        self.check_func = kwargs.get("check_func")
        if self.check_func:
            check_func_args = args
        else:
            self.check_func = args[0]
            check_func_args = args[1:]

        self.check_func_params = dict(
            zip(getfullargspec(self.check_func).args[1:], check_func_args))
        self.check_func_params.update(**kwargs)

    def __call__(self, f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            df = f(*args, **kwargs)
            if self.enabled:
                # differs from BaseDecorator
                ck.custom_check(df, self.check_func, **self.check_func_params)
            return df
        return decorated
