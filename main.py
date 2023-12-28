import asyncio
import logging
import os
from io import BytesIO
from xml.etree import ElementTree as ET

import aiohttp
import requests
from PIL import Image


class Manga:
    xml_url = "https://manga4life.com/rss"
    # image_url = "https://temp.compsci88.com/manga"
    image_url = "https://scans-hot.leanbox.us/manga"

    def __init__(self, name: str, path: str | None = None) -> None:
        self.name = name
        self.uid = name.capitalize().replace(" ", "-")
        self.slug = name.lower().replace(" ", "_")

        self.path = os.path.join(path or "data", self.slug)

        self.set_logger()

    def set_logger(self):
        file_handler = logging.FileHandler(f"{self.slug}.log", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        self.logger = logging.getLogger()
        self.logger.addHandler(file_handler)

        self.logger.setLevel(logging.DEBUG)

    def find_last_chapter(self) -> int:
        url_to_fetch = f"{self.xml_url}/{self.uid}.xml"

        response = requests.get(url_to_fetch)
        response.raise_for_status()

        tree = ET.fromstring(response.content)

        first_item = tree.find(".//item")
        assert first_item is not None, "item not found"

        guid = first_item.find("guid")
        assert guid is not None, "guid not found"

        last_chapter = guid.text
        assert last_chapter is not None, "last chapter not found"

        return int(last_chapter.split("-")[-1])

    async def download_page(self, chapter: int, page: int):
        image_url = f"{self.image_url}/{self.uid}/{chapter:04}-{page:03}.png"

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                try:
                    response.raise_for_status()

                except aiohttp.ClientResponseError as e:
                    self.logger.warning(f"Error in chapter {chapter}, page {page}: {e}")
                    raise e

                image = Image.open(BytesIO(await response.read()))
                image.save(
                    os.path.join(self.path, str(chapter).zfill(4), f"{page:03}.png")
                )

                self.logger.info(f"'{image_url}' downloaded successfully")

    async def _download_pages_in_chunks(self, chapter: int, window_size: int):
        page = 1
        while True:
            chunk = range(page, page + window_size)
            yield [self.download_page(chapter, page) for page in chunk]
            page += window_size

    async def download_chapter(self, chapter: int, window_size: int = 5):
        dir_path = os.path.join(self.path, str(chapter).zfill(4))
        os.makedirs(dir_path, exist_ok=True)

        async for page_group in self._download_pages_in_chunks(chapter, window_size):
            try:
                await asyncio.gather(*page_group)
            except aiohttp.ClientResponseError as e:
                break

    async def _download_chapters_in_chunks(self, chapters: range, window_size: int):
        while chapters:
            chunk = chapters[:window_size]
            chapters = chapters[window_size:]

            yield [self.download_chapter(chapter) for chapter in chunk]

    async def download_chapters(
        self, begin: int = 1, end: int = -1, window_size: int = 10
    ):
        if end == -1:
            end = self.find_last_chapter()

        chapters = range(begin, end + 1)
        async for chapter_group in self._download_chapters_in_chunks(
            chapters, window_size
        ):
            await asyncio.gather(*chapter_group)
            self.logger.info(f"{len(chapter_group)} chapters downloaded")

            self.logger.debug(f"sleeping for 300 seconds")
            await asyncio.sleep(300)

        self.logger.debug("done")


async def main():
    m = Manga(name)
    await m.download_chapters(165)


if __name__ == "__main__":
    name = "Vagabond"

    asyncio.run(main())
