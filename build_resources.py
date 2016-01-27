import logging
import os

_log = logging.getLogger(__name__)


def build_ui(src, dst, rel_import=False):
    cmd = "pyuic5 {} -o {}"
    if rel_import:
        cmd += " --from-imports"
    cmd = cmd.format(src, dst)
    _log.debug("cmd: %s", cmd)
    os.system(cmd)


def build_rc(src, dst):
    cmd = "pyrcc5 {} -o {}".format(src, dst)
    _log.debug("cmd: %s", cmd)
    os.system(cmd)


def build_resources(path, rel_import=False):
    """Данная функция рекурсивно проходит по всем каталогам начиная с
    указанного и ищет файлы с расширениями .ui и .qrc, а затем компилирует их
    в python модули."""
    for cur, dirs, files in os.walk(path):
        for filename in files:
            _log.debug(os.path.join(cur, filename))
            name, extension = os.path.splitext(filename)
            extension = extension.lower()
            if extension == '.ui':
                ui_module = "ui_" + name
                ui_module_path = os.path.join(cur, ui_module + '.py')
                if os.path.exists(ui_module_path):
                    _log.info("file already exists: %s", ui_module_path)
                    continue
                ui_path = os.path.join(cur, filename)
                build_ui(ui_path, ui_module_path, rel_import)
            elif extension == '.qrc':
                rc_path = os.path.join(cur, name + '_rc.py')
                if os.path.exists(rc_path):
                    _log.info("file already exists: %s", rc_path)
                    continue
                build_rc(os.path.join(cur, filename), rc_path)


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)
    sys.exit(build_resources('vkapi', True))
