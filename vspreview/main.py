from __future__ import annotations

import logging
from   pathlib import Path
import sys
from   typing  import Any, cast, Optional

from PySide2.QtCore    import QSize
from PySide2.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QMainWindow
)
import rx.operators as ops
from   vapoursynth  import VideoNode

from vspreview.core     import Frame, Output, Property, View, ViewModel
from vspreview.controls import ComboBox, GraphicsView, SpinBox, PushButton
from vspreview.models   import GraphicsScene, ListModel
from vspreview.utils    import Application, check_dependencies


class MainView(QMainWindow, View):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()  # pylint: disable=no-value-for-parameter
        View.__init__(self, *args, init_super=False, **kwargs)  # type: ignore

        self.setup_ui()

        self.setWindowTitle('VSPreview')

        self.graphics_view.bind_foreground_output(self._properties.current_output, View.BindKind.SOURCE_TO_VIEW)
        self.graphics_view.bind_outputs_model(self._data_context.outputs, View.BindKind.SOURCE_TO_VIEW)
        self.outputs_combobox.bind_current_item(self._properties.current_output, View.BindKind.BIDIRECTIONAL)
        self.outputs_combobox.bind_model(self._data_context.outputs, View.BindKind.SOURCE_TO_VIEW)
        self.frame_spinbox.bind_value(self._properties.current_frame, View.BindKind.BIDIRECTIONAL)
        self.frame_spinbox.bind_max_value(self._properties.last_frame, View.BindKind.SOURCE_TO_VIEW)
        self.load_button.bind(self._data_context.on_load_pressed, View.BindKind.VIEW_TO_SOURCE)

        ret = self.test_button.clicked.connect(self.on_test_clicked); assert ret

    def setup_ui(self) -> None:
        self.central_widget = QWidget(self)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.graphics_view = GraphicsView(self, GraphicsScene())
        self.main_layout.addWidget(self.graphics_view)

        self.toolbar_layout = QHBoxLayout()
        self.main_layout.addLayout(self.toolbar_layout)

        self.outputs_combobox = ComboBox(self)
        self.toolbar_layout.addWidget(self.outputs_combobox)

        self.frame_spinbox = SpinBox(self)
        self.toolbar_layout.addWidget(self.frame_spinbox)

        self.load_button = PushButton(self)
        self.load_button.setText('Load Script')
        self.toolbar_layout.addWidget(self.load_button)

        self.test_button = PushButton(self)
        self.test_button.setText('Resize')
        self.toolbar_layout.addWidget(self.test_button)

    def on_test_clicked(self, state: int) -> None:
        hint = self.graphics_view.sizeHint()
        new_size = QSize(hint.width() + 18, hint.height() + 47)
        self.resize(new_size)


class MainViewModel(ViewModel):
    current_frame  = Property[Frame](Frame(0))
    last_frame     = Property[Frame](Frame(0))
    current_output = Property[Optional[Output]](None)
    outputs = ListModel[Output]()

    def __init__(self) -> None:
        super().__init__()

        self.current_frame = type(self).current_output.pipe(
            ops.map(lambda output: output.current_frame if output is not None else Frame(0))
        )
        self.last_frame = type(self).current_output.pipe(
            ops.map(lambda output: output.last_frame if output is not None else Frame(0)),
        )

        type(self).current_frame.subscribe(self.switch_frame)  # type: ignore

    def switch_frame(self, frame: Frame) -> None:
        if self.current_output is None:
            return
        self.current_output.current_frame = frame

    def on_load_pressed(self) -> None:
        self.load_script(Path(r'script.vpy').resolve())

    def load_script(self, path: Path) -> None:
        from traceback import print_exc
        import vapoursynth as vs

        self.outputs.clear()
        vs.clear_outputs()

        sys.path.append(str(path.parent))
        try:
            exec(path.read_text(), {})  # pylint: disable=exec-used
        except Exception:  # pylint: disable=broad-except
            print_exc()
        finally:
            sys.path.pop()

        for i, vs_output in vs.get_outputs().items():
            self.outputs.append(Output(cast(VideoNode, vs_output), i))


def main() -> None:
    from argparse  import ArgumentParser
    from os        import chdir
    from .settings import LOG_LEVEL

    logging.basicConfig(format='{asctime}: {levelname}: {message}', style='{', level=LOG_LEVEL)
    logging.Formatter.default_msec_format = '%s.%03d'

    check_dependencies()

    parser = ArgumentParser()
    parser.add_argument('script_path', help='Path to Vapoursynth script', type=Path, nargs='?')
    args = parser.parse_args()

    if args.script_path is None:
        print('Script path required.')
        sys.exit(1)
    script_path = args.script_path.resolve()
    if not script_path.exists():
        print('Script path is invalid.')
        sys.exit(1)

    chdir(script_path.parent)

    app = Application(sys.argv)
    view_model = MainViewModel()
    view = MainView(view_model)
    view_model.load_script(script_path)
    view.show()  # type: ignore

    try:
        app.exec_()
    except Exception:  # pylint: disable=broad-except
        logging.error('app.exec_() exception')

if __name__ == '__main__':
    main()
