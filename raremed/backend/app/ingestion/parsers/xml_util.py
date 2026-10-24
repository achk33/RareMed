"""Shared XML helpers that tolerate namespace prefixes and official variants."""

from __future__ import annotations

from collections.abc import Iterator
from xml.etree.ElementTree import Element


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child(element: Element, *names: str) -> Element | None:
    wanted = {name.lower() for name in names}
    for item in list(element):
        if local_name(item.tag).lower() in wanted:
            return item
    return None


def children(element: Element, *names: str) -> list[Element]:
    wanted = {name.lower() for name in names}
    return [item for item in list(element) if local_name(item.tag).lower() in wanted]


def text_of(element: Element | None) -> str | None:
    if element is None:
        return None
    value = "".join(element.itertext()).strip()
    return value or None


def first_text(element: Element, *names: str) -> str | None:
    return text_of(child(element, *names))


def attr(element: Element, *names: str) -> str | None:
    lowered = {name.lower() for name in names}
    for key, value in element.attrib.items():
        if local_name(key).lower() in lowered and value:
            return value
    return None


def walk_named(element: Element, *names: str) -> Iterator[Element]:
    wanted = {name.lower() for name in names}
    if local_name(element.tag).lower() in wanted:
        yield element
    for item in list(element):
        yield from walk_named(item, *names)
