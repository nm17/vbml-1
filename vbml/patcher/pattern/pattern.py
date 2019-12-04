import re
from ..exceptions import PatternError
from ..standart import (
    PostValidation,
    AheadValidation,
    SYNTAX,
    UNION_CHAR,
    ONE_CHAR_CHAR,
    EXCEPT_CHAR,
    REGEX_CHAR,
    IGNORE_CHAR,
)
from typing import List, Tuple, Sequence, Optional


def flatten(lis):
    for item in lis:
        if isinstance(item, Sequence) and not isinstance(item, str):
            yield from flatten(item)
        else:
            yield item


ARG_PREFIX = "<"
ARG_SUFFIX = ">"


class Pattern:
    # Make whole text re-invisible
    escape = {ord(x): "\\" + x for x in r"\.*+?()[]|^${}:"}
    syntax = SYNTAX
    syntax_proc = {
        UNION_CHAR: PostValidation.union,
        ONE_CHAR_CHAR: PostValidation.one_char,
        EXCEPT_CHAR: PostValidation.except_of,
        REGEX_CHAR: PostValidation.regex_arg,
        IGNORE_CHAR: PostValidation.ignore_arg,
    }

    def __init__(
        self, text: str = None, pattern: str = "{}$", lazy: bool = True, **context
    ):
        text = text or ""
        findall = re.findall
        self._text = text

        # Find all arguments with validators
        typed_arguments = findall(r"(<.*?([a-zA-Z0-9_]+):.*?>)", text)

        # Save validators. Parse arguments
        self._validation, self._nested = PostValidation.get_validators(
            typed_arguments, context
        )

        # Delete arguments from regex
        text = re.sub(r"<(.*?)(?::[\[\]a-zA-Z_0-9, ]+)*>", r"<\1>", text)

        # Get all inclusions from regex
        inclusions: List[Optional[str]] = context.get("inclusions") or [
            PostValidation.inclusion(inc) for inc in findall("<(.*?)>", self._text)
        ]

        # Delete inclusion from regex
        text = re.sub(r"<(?:\(.*?\))(.*?)>", r"<\1>", text)

        # Add representation
        self._vbml = re.sub(r"<(.*?)>", context.get("repr_noun", "?"), text)

        ### Investigate final pattern
        # Set pattern constants
        self._arguments: list = findall("<(.*?)>", text)
        self._inclusions: dict = dict(zip(self.arguments, inclusions))
        self._ahead = AheadValidation(self.inclusions, self.nested)

        # Remove regex-incompatible symbols
        text = text.translate(self.escape)

        # Reveal arguments
        for arg in self.arguments:
            if arg == "":
                raise PatternError("Argument can't be empty")
            if arg[0] in self.syntax:
                text = text.replace(
                    "<{}>".format(arg.translate(self.escape)),
                    self.syntax_proc[arg[0]](
                        self.arguments, arg, self.inclusions, **context
                    ),
                )
            else:
                pre = self.inclusions.get(arg, "")
                text = text.replace(
                    "<{}>".format(arg),
                    "(?P<{arg}>{pre}.*{lazy})".format(
                        arg=arg,
                        pre=pre.translate(self.escape),
                        lazy="?" if lazy else "",
                    ),
                )

        self._compiler = re.compile(pattern.format(text), flags=context.get("flags", 0))
        self._pregmatch: Optional[dict] = None

    def __call__(self, text: str):
        """
        Check text for current pattern ignoring all features
        :param text:
        :return:
        """
        if not text:
            return
        match = self._compiler.match(text)
        if match is not None:
            self._pregmatch = self._ahead.group(match)
            return True

    @property
    def pattern(self):
        return self._compiler.pattern

    @property
    def validation(self):
        return self._validation

    @property
    def arguments(self):
        return self._arguments

    @property
    def inclusions(self):
        return self._inclusions

    @property
    def representation(self):
        return self._vbml

    @property
    def nested(self):
        return self._nested

    @property
    def text(self):
        return self._text

    def set_dict(self, new_dict: dict):
        self._pregmatch = new_dict
        return new_dict

    def remove_dict(self):
        self._pregmatch = None

    def dict(self):
        if self._pregmatch is None:
            raise PatternError(
                "Trying to get variables from text before matching text OR MATCHING WAS FAILED"
            )
        return self._pregmatch