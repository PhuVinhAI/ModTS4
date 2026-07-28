#    Copyright 2020 June Hanabi
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

# Helpers
import multiprocessing
import argparse

from util.decompile import decompile_mod_folder, decompile_pre, decompile_zips, decompile_print_totals
from settings import decompile_output_folder, gameplay_folder_data, gameplay_folder_game, projects_python_path


def build_parser():
    parser = argparse.ArgumentParser(description="Decompile script")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        '--folder', action='store_true',
        help="Decompile archives placed in decompile/input",
    )
    modes.add_argument('--game', action='store_true', help="Decompile game files")
    modes.add_argument(
        '--mod', metavar='MOD_FOLDER',
        help="Decompile an installed mod folder into decompile/output/mods",
    )
    return parser


def main(argv=None):
    multiprocessing.freeze_support()
    parser = build_parser()
    args = parser.parse_args(argv)

    # Do a pre-setup
    decompile_pre()

    # Decompile all zips to the python projects folder
    print("")
    print("Beginning decompilation")
    print("This may take a while! Some files may not decompile properly which is normal.")
    print("")


    if args.folder:
        decompile_zips("./decompile/input", projects_python_path)
    elif args.game:
        decompile_zips([gameplay_folder_data, gameplay_folder_game], projects_python_path)
    else:
        try:
            output_folder = decompile_mod_folder(args.mod, decompile_output_folder)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        print("Mod source written to: " + output_folder)

    # Print final statistics
    decompile_print_totals()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
