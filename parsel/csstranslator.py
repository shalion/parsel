from functools import lru_cache

from cssselect import GenericTranslator as OriginalGenericTranslator
from cssselect import HTMLTranslator as OriginalHTMLTranslator
from cssselect.parser import FunctionalPseudoElement
from cssselect.xpath import ExpressionError
from cssselect.xpath import XPathExpr as OriginalXPathExpr
from cssselect.xpath import _unicode_safe_getattr


class XPathExpr(OriginalXPathExpr):

    textnode = False
    attribute = None

    @classmethod
    def from_xpath(cls, xpath, textnode=False, attribute=None):
        x = cls(path=xpath.path, element=xpath.element, condition=xpath.condition)
        x.textnode = textnode
        x.attribute = attribute
        return x

    def __str__(self):
        path = super().__str__()
        if self.textnode:
            if path == "*":
                path = "text()"
            elif path.endswith("::*/*"):
                path = path[:-3] + "text()"
            else:
                path += "/text()"

        if self.attribute is not None:
            if path.endswith("::*/*"):
                path = path[:-2]
            path += f"/@{self.attribute}"

        return path

    def join(self, combiner, other):
        super().join(combiner, other)
        self.textnode = other.textnode
        self.attribute = other.attribute
        return self


class TranslatorMixin:
    """This mixin adds support to CSS pseudo elements via dynamic dispatch.

    Currently supported pseudo-elements are ``::text`` and ``::attr(ATTR_NAME)``.
    """

    def xpath_element(self, selector):
        xpath = super().xpath_element(selector)
        return XPathExpr.from_xpath(xpath)

    def xpath_pseudo_element(self, xpath, pseudo_element):
        """
        Dispatch method that transforms XPath to support pseudo-element
        """
        if isinstance(pseudo_element, FunctionalPseudoElement):
            pseudo_element_ = pseudo_element.name.replace("-", "_")
            method = f"xpath_{pseudo_element_}_functional_pseudo_element"
            method = _unicode_safe_getattr(self, method, None)
            if not method:
                raise ExpressionError(
                    "The functional pseudo-element ::"
                    f"{pseudo_element.name}() is unknown"
                )
            xpath = method(xpath, pseudo_element)
        else:
            pseudo_element_ = pseudo_element.replace("-", "_")
            method = f"xpath_{pseudo_element_}_simple_pseudo_element"
            method = _unicode_safe_getattr(self, method, None)
            if not method:
                raise ExpressionError(
                    f"The pseudo-element :: {pseudo_element} is unknown"
                )
            xpath = method(xpath)
        return xpath

    def xpath_attr_functional_pseudo_element(self, xpath, function):
        """Support selecting attribute values using ::attr() pseudo-element"""
        if function.argument_types() not in (["STRING"], ["IDENT"]):
            raise ExpressionError(
                "Expected a single string or ident for ::attr(),"
                f"got {function.arguments}"
            )
        return XPathExpr.from_xpath(xpath, attribute=function.arguments[0].value)

    def xpath_text_simple_pseudo_element(self, xpath):
        """Support selecting text nodes using ::text pseudo-element"""
        return XPathExpr.from_xpath(xpath, textnode=True)


class GenericTranslator(TranslatorMixin, OriginalGenericTranslator):
    @lru_cache(maxsize=256)
    def css_to_xpath(self, css, prefix="descendant-or-self::"):
        return super().css_to_xpath(css, prefix)


class HTMLTranslator(TranslatorMixin, OriginalHTMLTranslator):
    @lru_cache(maxsize=256)
    def css_to_xpath(self, css, prefix="descendant-or-self::"):
        return super().css_to_xpath(css, prefix)


_translator = HTMLTranslator()


def css2xpath(query):
    "Return translated XPath version of a given CSS query"
    return _translator.css_to_xpath(query)
