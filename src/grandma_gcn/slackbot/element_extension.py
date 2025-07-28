from typing import Self

from fink_utils.slack_bot.rich_text.rich_text_element import RichTextStyle


class RichTextElement:
    def __init__(self) -> None:
        """
        A class representing a rich text element.
        """
        super().__init__()
        self.element = {"type": "rich_text", "elements": []}

    def add_elements(self, elements: Self | list[Self]) -> Self:
        if type(elements) is list:
            self.element["elements"] += [el.get_element() for el in elements]
        else:
            self.element["elements"].append(elements.get_element())
        return self

    def get_element(self) -> dict:
        return self.element


class Text:
    def __init__(self, text: str, style: RichTextStyle = None) -> None:
        """
        A text element

        Parameters
        ----------
        text : str
            text
        style : RichTextStyle, optional
            text style, by default None
        """
        super().__init__()
        self.text = {"type": "text", "text": text}
        if style is not None:
            self.text["style"] = {style.value: True}

    def get_element(self):
        return self.text

    def set_emoji(self, emoji: bool) -> Self:
        """
        Set whether the text should be treated as an emoji.

        Parameters
        ----------
        emoji : bool
            Whether to treat the text as an emoji.

        Returns
        -------
        Self
            The updated text element.
        """
        self.text["emoji"] = emoji
        return self

    def add_style(self, style: RichTextStyle) -> Self:
        """
        Set the style of the text element.

        Parameters
        ----------
        style : RichTextStyle
            The style to set.

        Returns
        -------
        Self
            The updated text element.
        """
        self.text["style"][style.value] = True
        return self


class BaseSection:
    def __init__(self) -> None:
        """
        A class representing a section.
        """
        super().__init__()
        self.section = {"type": "section"}

    def add_elements(self, elements: RichTextElement | list[RichTextElement]) -> Self:
        if "fields" not in self.section:
            self.section["fields"] = []

        if type(elements) is list:
            self.section["fields"] += [el.get_element() for el in elements]
        else:
            self.section["fields"].append(elements.get_element())
        return self

    def add_text(self, text: Text) -> Self:
        """
        Add a text element to the section.

        Parameters
        ----------
        text : Text
            The text element to add.

        Returns
        -------
        Self
            The updated section.
        """
        if "text" not in self.section:
            self.section["text"] = text.get_element()
        return self

    def add_accessory(self, accessory: dict) -> Self:
        """
        Add an accessory to the section.

        Parameters
        ----------
        accessory : dict
            The accessory to add.

        Returns
        -------
        Self
            The updated section.
        """
        self.section["accessory"] = accessory.get_element()
        return self

    def get_element(self) -> dict:
        return self.section


class MarkdownText(Text):
    def __init__(self, text: str) -> None:
        """
        A markdown text element

        Parameters
        ----------
        text : str
            text
        """
        super().__init__(text=text)
        self.text["type"] = "mrkdwn"


class PlainText(Text):
    def __init__(self, text: str, emoji: bool = False) -> None:
        """
        A plain text element

        Parameters
        ----------
        text : str
            text
        emoji : bool, optional
            whether the text should be treated as an emoji, by default False
        """
        super().__init__(text=text)
        self.text["type"] = "plain_text"
        self.text["emoji"] = emoji


class URLButton:
    def __init__(self, text: str, emoji: bool) -> None:
        """
        A button element

        Parameters
        ----------
        text : str
            text
        url : str
            url
        """
        super().__init__()
        self.button = {
            "type": "button",
            "text": {"type": "plain_text", "text": text, "emoji": emoji},
        }

    def get_element(self) -> dict:
        return self.button

    def add_url(self, url: str) -> Self:
        """
        Set the URL for the button.

        Parameters
        ----------
        url : str
            The URL to set.

        Returns
        -------
        Self
            The updated button element.
        """
        self.button["url"] = url
        return self


class Action:
    def __init__(self) -> None:
        """
        A class representing an action.
        """
        super().__init__()
        self.action = {"type": "actions", "elements": []}

    def add_elements(self, elements: URLButton | list[URLButton]) -> Self:
        if type(elements) is list:
            self.action["elements"] += [el.get_element() for el in elements]
        else:
            self.action["elements"].append(elements.get_element())
        return self

    def get_element(self) -> dict:
        return self.action
