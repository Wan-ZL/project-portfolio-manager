from textual.binding import Binding

PORTFOLIO_BINDINGS = [
    Binding("q", "quit", "Quit"),
    Binding("j,down", "cursor_down", "Down", show=False),
    Binding("k,up", "cursor_up", "Up", show=False),
    Binding("tab", "next_tab", "Next Tab"),
    Binding("shift+tab", "prev_tab", "Prev Tab"),
    Binding("enter", "enter_project", "Open"),
    Binding("n", "new_task", "New Task"),
    Binding("r", "refresh", "Refresh"),
    Binding("question_mark", "help", "Help"),
]

PROJECT_BINDINGS = [
    Binding("escape", "go_back", "Back"),
    Binding("j,down", "cursor_down", "Down", show=False),
    Binding("k,up", "cursor_up", "Up", show=False),
    Binding("tab", "next_tab", "Next Tab"),
    Binding("shift+tab", "prev_tab", "Prev Tab"),
    Binding("enter", "select_item", "Select"),
    Binding("a", "attach_session", "Attach"),
    Binding("n", "new_task", "New Task"),
    Binding("f", "fix_pr", "Fix PR"),
    Binding("m", "merge_pr", "Merge"),
]

TASK_BINDINGS = [
    Binding("escape", "go_back", "Back"),
    Binding("ctrl+q", "detach_session", "Detach"),
    Binding("p", "pause_session", "Pause"),
    Binding("k", "kill_session", "Kill"),
    Binding("r", "reprompt", "Reprompt"),
]
