# Copyright (c) Streamlit Inc. (2018-2022) Snowflake Inc. (2022-2024)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import unittest

from parameterized import parameterized

from streamlit.errors import StreamlitAPIException
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from streamlit.runtime.fragment import MemoryFragmentStorage
from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
from streamlit.runtime.pages_manager import PagesManager
from streamlit.runtime.scriptrunner import ScriptRunContext
from streamlit.runtime.state import SafeSessionState, SessionState


class ScriptRunContextTest(unittest.TestCase):
    def test_set_page_config_immutable(self):
        """st.set_page_config must be called at most once"""

        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )

        msg = ForwardMsg()
        msg.page_config_changed.title = "foo"

        ctx.enqueue(msg)
        with self.assertRaises(StreamlitAPIException):
            ctx.enqueue(msg)

    def test_set_page_config_first(self):
        """st.set_page_config must be called before other st commands
        when the script has been marked as started"""

        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )

        ctx.on_script_start()

        markdown_msg = ForwardMsg()
        markdown_msg.delta.new_element.markdown.body = "foo"

        msg = ForwardMsg()
        msg.page_config_changed.title = "foo"

        ctx.enqueue(markdown_msg)
        with self.assertRaises(StreamlitAPIException):
            ctx.enqueue(msg)

    def test_disallow_set_page_config_twice(self):
        """st.set_page_config cannot be called twice"""

        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )

        ctx.on_script_start()

        msg = ForwardMsg()
        msg.page_config_changed.title = "foo"
        ctx.enqueue(msg)

        with self.assertRaises(StreamlitAPIException):
            same_msg = ForwardMsg()
            same_msg.page_config_changed.title = "bar"
            ctx.enqueue(same_msg)

    def test_set_page_config_reset(self):
        """st.set_page_config should be allowed after a rerun"""

        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )

        ctx.on_script_start()

        msg = ForwardMsg()
        msg.page_config_changed.title = "foo"

        ctx.enqueue(msg)
        ctx.reset()
        try:
            ctx.on_script_start()
            ctx.enqueue(msg)
        except StreamlitAPIException:
            self.fail("set_page_config should have succeeded after reset!")

    def test_active_script_hash(self):
        """ensures active script hash is set correctly when enqueueing messages"""

        fake_path = "my/custom/script/path"
        pg_mgr = PagesManager(fake_path)

        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=pg_mgr,
        )

        ctx.on_script_start()

        msg = ForwardMsg()
        msg.delta.new_element.markdown.body = "foo"

        ctx.enqueue(msg)
        self.assertEqual(
            msg.metadata.active_script_hash, pg_mgr.get_active_script_hash()
        )

        pg_mgr.set_current_page_script_hash("new_hash")

        new_msg = ForwardMsg()
        new_msg.delta.new_element.markdown.body = "bar"

        ctx.enqueue(new_msg)
        self.assertEqual(new_msg.metadata.active_script_hash, "new_hash")

    @parameterized.expand(
        [
            (True, True, True),  # Both APIs used
            (True, False, False),  # Only experimental API used
            (False, True, False),  # Only final API used
            (False, False, False),  # Neither API used
        ]
    )
    def test_both_query_params_used(
        self, experimental_used, production_used, should_raise
    ):
        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )
        ctx._experimental_query_params_used = experimental_used
        ctx._production_query_params_used = production_used

        if should_raise:
            with self.assertRaises(StreamlitAPIException):
                ctx.ensure_single_query_api_used()
        else:
            ctx.ensure_single_query_api_used()

    def test_mark_experimental_query_params_used_sets_true(self):
        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )
        ctx.mark_experimental_query_params_used()
        assert ctx._experimental_query_params_used is True

    def test_mark_production_query_params_used_sets_true(self):
        def fake_enqueue(msg):
            return None

        ctx = ScriptRunContext(
            session_id="TestSessionID",
            _enqueue=fake_enqueue,
            query_string="",
            session_state=SafeSessionState(SessionState(), lambda: None),
            uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
            main_script_path="",
            user_info={"email": "test@test.com"},
            fragment_storage=MemoryFragmentStorage(),
            pages_manager=PagesManager(""),
        )
        ctx.mark_production_query_params_used()
        assert ctx._production_query_params_used is True
