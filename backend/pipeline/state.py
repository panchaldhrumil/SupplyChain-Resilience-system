"""
state.py
========
Mutable pipeline state passed between stages.
"""


class PipelineState:
    """
    Lightweight container for shared pipeline runtime state.
    Passed between pipeline stages so each stage doesn't need global variables.
    """

    def __init__(self):
        self.conn = None
        self.run_id = None
        self.existing_hashes: set = set()
        self.all_items: list = []
        self.df_filtered = None
