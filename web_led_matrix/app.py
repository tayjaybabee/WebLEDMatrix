from threading import Thread
import streamlit as st
from is_matrix_forge.led_matrix.controller.helpers import get_controllers
import time


class MatrixControllerApp:
    """
    A Streamlit app to select LED matrices and run an identify routine on them.
    Supports concurrent identification with visual feedback.
    """

    def __init__(self):
        self.controllers = get_controllers()
        self.controller_names = [c.name for c in self.controllers]

        if 'processing' not in st.session_state:
            st.session_state.processing = False
        if 'identify_threads' not in st.session_state:
            st.session_state.identify_threads = []

    def _identify_controller(self, controller):
        controller.identify()

    def handle_identify(self):
        selected = st.session_state.select_matrix
        threads = []

        if selected == 'All':
            for ctrl in self.controllers:
                t = Thread(target=self._identify_controller, args=(ctrl,), daemon=True)
                threads.append(t)
        else:
            idx = self.controller_names.index(selected)
            t = Thread(target=self._identify_controller, args=(self.controllers[idx],), daemon=True)
            threads.append(t)

        st.session_state.identify_threads = threads
        st.session_state.processing = True

        for thread in threads:
            thread.start()

        st.rerun()

    def run(self):
        threads = st.session_state.identify_threads
        if threads:
            if all(not t.is_alive() for t in threads):
                st.session_state.processing = False
                st.session_state.identify_threads = []

        st.title("LED Matrix Control")

        disabled = st.session_state.processing or bool(st.session_state.identify_threads)

        selected_matrix = st.selectbox(
            "Select a matrix",
            options=self.controller_names + ["All"],
            key="select_matrix",
            disabled=disabled,
        )

        if st.button("Identify", disabled=disabled):
            self.handle_identify()

        if disabled:
            with st.spinner("Identifying..."):
                while any(t.is_alive() for t in st.session_state.identify_threads):
                    time.sleep(0.1)
                st.rerun()


if __name__ == "__main__":
    MatrixControllerApp().run()
