import logging
import inspect
import pprint
import ctypes
import os

import pych.runtime

typemap = {
    None:       None,
    bool:       ctypes.c_bool,
    int:        ctypes.c_int,
    long:       ctypes.c_long,
    float:      ctypes.c_double,
    str:        ctypes.c_char_p,
    unicode:    ctypes.c_wchar_p
}

class Extern(object):
    """
    Encapsulates a mapping between a Python function and an external function.
    """

    def __init__(self, pfunc=None, pname=None, doc=None,
                 atypes=[], anames=[], rtype=None,
                 efunc=None, ename=None, elib=None,
                 sfile=None, slang=None):

        self.pfunc  = pfunc     # Python function handle
        self.pname  = pname     # Python function name
        self.doc    = doc       # Python doc-string (used for inline source-code)
        self.atypes = atypes    # Python types of function arguments
        self.anames = anames    # Python names of function arguments
        self.rtype  = rtype     # Python type for the return value

        self.efunc  = efunc     # ctypes function handle
        self.ename  = ename     # External function name
        self.elib   = elib      # Library filename
        self.sfile  = sfile     # File with sourcecode
        self.slang  = slang     # Language of the 

    def __repr__(self):
        return pprint.pformat(vars(self))

#
# Decorate a Python-function with these to construct a mapping to an Extern.
#
class FromExtern(object):
    """Encapsulates a call to an external function."""

    def __init__(self, ename=None, elib=None, sfile=None, slang=None):

        # This is done only once; when the function is decorated
        self._extern = Extern(
            pfunc   = None,
            pname   = None,
            doc     = None,
            atypes  = [],
            anames  = [],
            rtype   = None,

            efunc   = None,
            ename   = ename,
            elib    = elib,

            sfile   = sfile,
            slang   = slang
        )
        logging.debug("__init__decorate__")

    def _validate_decl(self):
        """Validate the function declaration."""

        if len(self._extern.atypes) != len(self._extern.anames):
            # Check that we have sufficient amount of type-declarations
            raise TypeError("Missing type declaration on arguments.")
        else:
            # Check that declared types are supported
            for i, arg in enumerate(self._extern.anames):
                arg_type = self._extern.atypes[i]
                if arg_type not in typemap:
                    msg = "Unsupported type: %s for argument %s" % (
                        arg_type, arg
                    )
                    raise TypeError(msg)

    def _type_check(self, args):
        """Compare argument-types with extern declation."""

        call_types = [type(arg) for arg in args]
        if call_types != self._extern.atypes:
            ct_text = pprint.pformat(call_types)
            at_text = pprint.pformat(self._extern.atypes)
            raise TypeError("Unsupported arg-types; %s. Expected: %s" %
                            (ct_text, at_text))

    def __call__(self, f):
        # This is done only once; when the function is decorated

        self._extern.pfunc  = f
        self._extern.pname  = f.__name__
        self._extern.doc    = f.__doc__

        #
        # Infer type-declaration of Extern from the crazy convention
        arg_spec = inspect.getargspec(self._extern.pfunc)

        self._extern.anames = arg_spec.args         # Extract argument names
        if arg_spec.defaults:                       # Extract argument types
            self._extern.atypes = list(arg_spec.defaults)
        self._extern.rtype  = self._extern.pfunc()  # Obtain return-type

        self._validate_decl()                       # Validate declaration

        # 
        # Extract attributes for "inline" function
        if self._extern.doc:
            self._extern.ename = self._extern.pname
            self._extern.elib  = "inline.so"

        #
        # Extract attributes for "sfile" function
        if self._extern.sfile:
            # TODO: Consider parsing the source-file and expanding validation
            #       of the type-declaration using the parsed information.
            if not self._extern.ename:
                self._extern.ename = self._extern.pname

            self._extern.elib = "lib%s.so" % os.path.splitext(os.path.basename(
                self._extern.sfile
            ))[0]

        #
        # Hint the runtime that we might want to call this Extern in
        # the future.
        # This could be used as a means of compiling the
        # function ahead of time. Or compile all hinted functions
        # in one go as the first call hits a function.
        #
        pych.runtime.instance.hint(self._extern)

        def wrapped_f(*args):
            # This is invoked on each function-call
            logging.debug("__actual_call__")

            self._type_check(args)      # Typecheck actuals with declaration

            #
            # Obtain the external object.
            if not self._extern.efunc:
                efunc = pych.runtime.instance.materialize(self._extern)

                if not efunc:
                    raise Exception("Failed materializing function!")
                #
                # Register argument conversion functions on efunc
                efunc.argtypes = [typemap[atype] for atype in self._extern.atypes]
                efunc.restype  = typemap[self._extern.rtype]

                #
                # Register the efunc handle on Extern
                self._extern.efunc = efunc

            #
            # Call
            return self._extern.efunc(*args)

        return wrapped_f

class FromC(FromExtern):

    def __init__(self, ename=None, elib=None, sfile=None):
        super(FromC, self).__init__(
            ename = ename,
            elib = elib,

            sfile = sfile,
            slang = "C"
        )

class FromChapel(FromExtern):

    def __init__(self, ename=None, elib=None, sfile=None):
        super(FromChapel, self).__init__(
            ename = ename,
            elib = elib,

            sfile = sfile,
            slang = "Chapel"
        )

