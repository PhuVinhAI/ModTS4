"""Build the tuning package for the Xem Anime television interaction."""

import os

import settings
from util.anime_package import build_anime_package


def main():
    output_path = os.path.join(settings.assets_path, "tomis_AnimeTV.package")
    build_anime_package(settings.game_folder, output_path)
    print("Built {}".format(output_path))


if __name__ == "__main__":
    main()
