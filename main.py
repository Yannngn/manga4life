import asyncio
import os
from io import BytesIO
from xml.etree import ElementTree as ET

import aiohttp
import requests
from PIL import Image


class Manga:
    main_url = "https://manga4life.com/manga"
    xml_url = "https://manga4life.com/rss"
    html_url = "https://manga4life.com/read-online"
    image_url = "https://temp.compsci88.com/manga"

    def __init__(self, name: str) -> None:
        self.name = name
        self.uid = name.capitalize().replace(" ", "-")
        self.slug = name.lower().replace(" ", "_")

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

    async def download_chapter(self, chapter: int, patience: int = 3, limit: int = 100):
        dir_path = os.path.join("data", self.slug, str(chapter).zfill(4))
        os.makedirs(dir_path, exist_ok=True)

        page = 1
        counter = 0
        while page < limit and counter < patience:
            try:
                await self.download_page(chapter, page)

            except aiohttp.ClientResponseError as e:
                print(f"Error in chapter {chapter}, page {page}: {e}")
                counter += 1

            page += 1

    async def download_page(self, chapter: int, page: int):
        image_url = f"{self.image_url}/{self.uid}/{chapter:04}-{page:03}.png"

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                response.raise_for_status()

                image = Image.open(BytesIO(await response.read()))
                image.save(
                    os.path.join(self.slug, str(chapter).zfill(4), f"{page:03}.png")
                )

    async def download_all_chapters(
        self, start: int = 1, end: int = -1, limit: int = 100
    ):
        if end == -1:
            end = self.find_last_chapter()

        tasks = [
            asyncio.create_task(self.download_chapter(chapter, limit=limit))
            for chapter in range(start, end + 1)
        ]

        await asyncio.gather(*tasks)


async def main():
    m = Manga("vagabond")
    await m.download_all_chapters()


if __name__ == "__main__":
    asyncio.run(main())


# # Example usage:
# base_url = "https://example.com/page/"  # Replace with the actual base URL
# start_page = 1  # Adjust as needed
# end_page = 5  # Adjust as needed
# generate_pdf_from_url(base_url, start_page, end_page)
