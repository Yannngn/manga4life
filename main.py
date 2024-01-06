import asyncio
import logging
import os
import re
from io import BytesIO
from xml.etree import ElementTree as ET

import aiohttp
import requests
from PIL import Image
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By


class Manga:
    main_url = "https://manga4life.com"
    pattern = r".*(?:[0-9]{4}-[0-9]{3})\.png$"

    def __init__(self, name: str, path: str | None = None) -> None:
        self.name = name
        self.uid = name.title().replace(" ", "-")
        self.slug = name.lower().replace(" ", "_")

        self.path = os.path.join(path or "data", self.slug)

        self.set_logger()

    async def download_chapters(
        self,
        begin: int = 1,
        end: int = -1,
        concurrent_chapters: int = 3,
        concurrent_downloads: int = 10,
    ):
        if end == -1:
            end = self.find_last_chapter()

        for chunk_start in range(begin, end + 1, concurrent_chapters):
            chunk_end = min(chunk_start + concurrent_chapters - 1, end)

            tasks = [
                asyncio.create_task(
                    self.run_driver_and_download(idx, concurrent_downloads)
                )
                for idx in range(chunk_start, chunk_end + 1)
            ]
            await asyncio.gather(*tasks)

        self.logger.debug("done")

    async def run_driver_and_download(self, idx: int, window_size: int):
        images = await self.run_driver(idx)
        await self.download_images(images, window_size)

    async def run_driver(self, chapter: int) -> list[str]:
        dir_path = os.path.join(self.path, str(chapter).zfill(4))
        os.makedirs(dir_path, exist_ok=True)

        driver = WebDriver()
        driver.get(f"{self.main_url}/read-online/{self.uid}-chapter-{chapter}.html")

        images = self.get_images_src(driver)

        driver.quit()

        if len(images) == 0:
            logging.warning("No images were found")

        return images

    def get_images_src(self, driver: WebDriver) -> list[str]:
        driver.implicitly_wait(10)
        images = driver.find_elements(By.TAG_NAME, "img")
        sources = [img.get_attribute("src") for img in images]

        for i, source in enumerate(sources):
            if source is None:
                logging.warning(f"index {i} was None")

        filtered_sources = [
            str(source) for source in sources if re.match(self.pattern, str(source))
        ]

        return filtered_sources

    async def download_images(self, images: list[str], window_size: int = 5):
        semaphore = asyncio.Semaphore(window_size)

        async def download_with_limit(url):
            async with semaphore:
                return await self.download_image(url)

        tasks = [asyncio.create_task(download_with_limit(url)) for url in images]
        await asyncio.gather(*tasks)

    async def download_image(self, image_url: str):
        chapter, page = self._extract_chapter_page(image_url)

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                try:
                    response.raise_for_status()

                except aiohttp.ClientResponseError as e:
                    self.logger.error(f"Error in {image_url}: {e}")
                    raise e

                image = Image.open(BytesIO(await response.read()))
                image.save(os.path.join(self.path, chapter, f"{page}.png"))

                self.logger.info(f"'{image_url}' downloaded successfully")

    @staticmethod
    def _extract_chapter_page(url: str) -> tuple[str, str]:
        info = url.split("/")[-1].split(".")[0]

        chapter, page = info.split("-")

        return chapter, page

    def set_logger(self):
        file_handler = logging.FileHandler(f"{self.slug}.log", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        self.logger = logging.getLogger()
        self.logger.addHandler(file_handler)

        self.logger.setLevel(logging.INFO)

    def find_last_chapter(self) -> int:
        url_to_fetch = f"https://manga4life.com/rss/{self.uid}.xml"

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


async def main():
    m = Manga(name)

    await m.download_chapters(1, 11)


if __name__ == "__main__":
    name = "chainsaw man color"

    asyncio.run(main())
