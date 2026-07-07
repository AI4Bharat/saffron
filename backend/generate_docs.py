import argparse
import json
import os
import re
import sys
from collections import defaultdict

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ILLEGAL_CHARACTERS_RE = re.compile(r'[\000-\010\013\014\016-\037]')
DEFAULT_LANGUAGE = 'english'

ALLOWED_GRADES = {"secondary", "senior_secondary", "elementary","middle"}

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
SET_NUMBER = 1


def matches_version(file_path, version_query):
    if not version_query:
        return True
    
    path_lower = file_path.lower()
    query_lower = str(version_query).strip().lower()
    
    if query_lower.isdigit():
        patterns = [
            f"version_{query_lower}",
            f"version{query_lower}",
            f"/v{query_lower}/",
            f"_v{query_lower}_",
            f"v_{query_lower}"
        ]
        parts = re.split(r'[/\\_.-]', path_lower)
        if query_lower in parts or any(p in path_lower for p in patterns):
            return True
        return False
    else:
        return query_lower in path_lower or query_lower.replace('_', '') in path_lower.replace('_', '')


def parse_task_ids(task_ids_str):
    if not task_ids_str:
        return None
    ids = set()
    for part in task_ids_str.split(','):
        part = part.strip()
        if '-' in part:
            try:
                start_str, end_str = part.split('-')
                start_val = int(start_str.strip())
                end_val = int(end_str.strip())
                for val in range(start_val, end_val + 1):
                    ids.add(val)
            except ValueError:
                pass
        else:
            try:
                ids.add(int(part))
            except ValueError:
                pass
    return ids


def matches_task_id(file_path, start_id=None, end_id=None, task_ids_set=None):
    filename = os.path.basename(file_path)
    # Find leading numbers
    match = re.match(r'^(\d+)', filename)
    if not match:
        # If no leading number, it fails the ID filter if any filter is active
        if start_id is not None or end_id is not None or task_ids_set is not None:
            return False
        return True
    
    file_id = int(match.group(1))
    
    if task_ids_set is not None and file_id not in task_ids_set:
        return False
    if start_id is not None and file_id < start_id:
        return False
    if end_id is not None and file_id > end_id:
        return False
        
    return True

    
PERSONA_ORDER = [
    "calm_explainer",
    "energetic_enthusiast",
    "reflective_mentor",
    "relatable_peer",
    "socratic_challenger",
    "storyteller",
    "strict_disciplinarian",
    "warm_encourager",
]


GRADE_DISPLAY = {
    "secondary": "Secondary",
    "senior_secondary": "Senior Secondary",
    "elementary": "Elementary",
    "middle": "Middle School",
}


# ---------------------------------------------------------------------------
# Comprehensive Unicode symbol tables
# ---------------------------------------------------------------------------

SUB_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ', 'i': 'ᵢ',
    'r': 'ᵣ', 'u': 'ᵤ', 'v': 'ᵥ', 'j': 'ⱼ', 'k': 'ₖ',
    'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'p': 'ₚ', 's': 'ₛ',
    't': 'ₜ', 'h': 'ₕ', 'g': 'ᵍ',  # ᵍ is superscript but often used
}

SUP_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'o': 'ᵒ', 'i': 'ⁱ', 'a': 'ᵃ', 'b': 'ᵇ',
    'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ',
    'h': 'ʰ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ',
    'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
    'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
    'A': 'ᴬ', 'B': 'ᴮ', 'D': 'ᴰ', 'E': 'ᴱ', 'G': 'ᴳ',
    'H': 'ᴴ', 'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ',
    'M': 'ᴹ', 'N': 'ᴺ', 'O': 'ᴼ', 'P': 'ᴾ', 'R': 'ᴿ',
    'T': 'ᵀ', 'U': 'ᵁ', 'V': 'ⱽ', 'W': 'ᵂ',
}

# Greek letters
GREEK = {
    r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
    r'\epsilon': 'ε', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η',
    r'\theta': 'θ', r'\vartheta': 'ϑ', r'\iota': 'ι', r'\kappa': 'κ',
    r'\lambda': 'λ', r'\mu': 'μ', r'\nu': 'ν', r'\xi': 'ξ',
    r'\pi': 'π', r'\varpi': 'ϖ', r'\rho': 'ρ', r'\varrho': 'ϱ',
    r'\sigma': 'σ', r'\varsigma': 'ς', r'\tau': 'τ', r'\upsilon': 'υ',
    r'\phi': 'φ', r'\varphi': 'φ', r'\chi': 'χ', r'\psi': 'ψ',
    r'\omega': 'ω',
    r'\Gamma': 'Γ', r'\Delta': 'Δ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
    r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ', r'\Upsilon': 'Υ',
    r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
}

# Math operators, relations, arrows, misc symbols
SYMBOLS = {
    # Operators
    r'\times': '×', r'\div': '÷', r'\cdot': '·', r'\pm': '±', r'\mp': '∓',
    r'\circ': '∘', r'\bullet': '•', r'\oplus': '⊕', r'\otimes': '⊗',
    r'\odot': '⊙', r'\oslash': '⊘', r'\cap': '∩', r'\cup': '∪',
    r'\setminus': '∖', r'\ast': '∗', r'\star': '★', r'\dagger': '†',
    r'\ddagger': '‡', r'\amalg': '⨿', r'\wedge': '∧', r'\vee': '∨',
    r'\land': '∧', r'\lor': '∨',
    # Relations
    r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\approx': '≈',
    r'\equiv': '≡', r'\sim': '∼', r'\simeq': '≃', r'\cong': '≅',
    r'\propto': '∝', r'\perp': '⊥', r'\parallel': '∥', r'\mid': '∣',
    r'\nmid': '∤', r'\subset': '⊂', r'\supset': '⊃', r'\subseteq': '⊆',
    r'\supseteq': '⊇', r'\in': '∈', r'\notin': '∉', r'\ni': '∋',
    r'\ll': '≪', r'\gg': '≫', r'\prec': '≺', r'\succ': '≻',
    r'\preceq': '⪯', r'\succeq': '⪰', r'\not\\subset': '⊄',
    r'\le': '≤', r'\ge': '≥', r'\ne': '≠',
    # Arrows
    r'\to': '→', r'\gets': '←', r'\rightarrow': '→', r'\leftarrow': '←',
    r'\Rightarrow': '⇒', r'\Leftarrow': '⇐', r'\Leftrightarrow': '⟺',
    r'\leftrightarrow': '↔', r'\longrightarrow': '⟶', r'\longleftarrow': '⟵',
    r'\uparrow': '↑', r'\downarrow': '↓', r'\updownarrow': '↕',
    r'\Uparrow': '⇑', r'\Downarrow': '⇓', r'\nearrow': '↗',
    r'\searrow': '↘', r'\swarrow': '↙', r'\nwarrow': '↖',
    r'\mapsto': '↦', r'\hookrightarrow': '↪', r'\hookleftarrow': '↩',
    r'\rightharpoonup': '⇀', r'\leftharpoonup': '↼',
    # Sets / logic
    r'\emptyset': '∅', r'\varnothing': '∅', r'\forall': '∀', r'\exists': '∃',
    r'\nexists': '∄', r'\neg': '¬', r'\lnot': '¬', r'\top': '⊤', r'\bot': '⊥',
    r'\vdash': '⊢', r'\models': '⊨', r'\therefore': '∴', r'\because': '∵',
    # Calculus / analysis
    r'\partial': '∂', r'\nabla': '∇', r'\infty': '∞', r'\aleph': 'ℵ',
    r'\hbar': 'ℏ', r'\ell': 'ℓ', r'\Re': 'ℜ', r'\Im': 'ℑ', r'\wp': '℘',
    r'\prime': '′', r'\backprime': '‵',
    # Misc
    r'\ldots': '…', r'\cdots': '⋯', r'\vdots': '⋮', r'\ddots': '⋱',
    r'\angle': '∠', r'\triangle': '△', r'\square': '□', r'\diamond': '◇',
    r'\langle': '⟨', r'\rangle': '⟩',
    r'\lceil': '⌈', r'\rceil': '⌉', r'\lfloor': '⌊', r'\rfloor': '⌋',
    r'\checkmark': '✓', r'\dag': '†',
    # Big operators (rendered as unicode)
    r'\sum': 'Σ', r'\prod': 'Π', r'\int': '∫', r'\oint': '∮',
    r'\iint': '∬', r'\iiint': '∭', r'\bigcup': '⋃', r'\bigcap': '⋂',
    r'\bigoplus': '⨁', r'\bigotimes': '⨂', r'\bigsqcup': '⊔',
    # Number sets
    r'\mathbb{R}': 'ℝ', r'\mathbb{Z}': 'ℤ', r'\mathbb{N}': 'ℕ',
    r'\mathbb{Q}': 'ℚ', r'\mathbb{C}': 'ℂ', r'\mathbb{P}': 'ℙ',
}

# Named functions → just strip backslash
NAMED_FUNCTIONS = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
    'log', 'ln', 'lg', 'exp', 'lim', 'liminf', 'limsup',
    'max', 'min', 'sup', 'inf', 'arg', 'det', 'dim',
    'ker', 'rank', 'trace', 'tr', 'deg', 'gcd', 'lcm',
    'mod', 'Pr', 'Var', 'cov', 'sgn', 'sign',
}


# ---------------------------------------------------------------------------
# Comprehensive LaTeX → plain-text renderer
# ---------------------------------------------------------------------------

def _chars_to_sub(s: str) -> str:
    return ''.join(SUB_MAP.get(ch, ch) for ch in s)


def _chars_to_sup(s: str) -> str:
    return ''.join(SUP_MAP.get(ch, ch) for ch in s)


def _render_latex_expr(expr: str) -> str:
    """
    Recursively convert a LaTeX math expression (without surrounding $ delimiters)
    into a human-readable Unicode string.
    """
    # ---- multiline environments → flatten with newlines ----
    expr = re.sub(
        r'\\begin\{(?:align\*?|gather\*?|equation\*?|cases|pmatrix|bmatrix|vmatrix|matrix|array)\}'
        r'(.*?)'
        r'\\end\{(?:align\*?|gather\*?|equation\*?|cases|pmatrix|bmatrix|vmatrix|matrix|array)\}',
        lambda m: m.group(1).replace('\\\\', '; ').replace('&', ' '),
        expr, flags=re.DOTALL,
    )

    # ---- \text{...} and similar wrappers → plain text ----
    for cmd in (r'\\text', r'\\textrm', r'\\textbf', r'\\textit',
                r'\\mathrm', r'\\mathbf', r'\\mathit', r'\\mathsf',
                r'\\mathtt', r'\\mathcal', r'\\mathfrak', r'\\boldsymbol',
                r'\\bm', r'\\operatorname'):
        expr = re.sub(cmd + r'\{([^{}]*)\}', r'\1', expr)

    # ---- \mathbb{X} → number-set symbols ----
    for key, val in SYMBOLS.items():
        if key.startswith(r'\mathbb'):
            expr = expr.replace(key, val)

    # ---- degree: ^{\circ} — must come BEFORE \circ is converted to ∘ ----
    expr = re.sub(r'\^\{\\circ\}', '°', expr)
    expr = re.sub(r'\^\\circ(?=[^a-zA-Z]|$)', '°', expr)

    # ---- Greek letters & named symbols ----
    for key, val in GREEK.items():
        # Use word-boundary-style replacement to avoid partial matches
        expr = re.sub(re.escape(key) + r'(?=[^a-zA-Z]|$)', val, expr)
    for key, val in SYMBOLS.items():
        if not key.startswith(r'\mathbb'):
            expr = re.sub(re.escape(key) + r'(?=[^a-zA-Z]|$)', val, expr)

    # ---- Named math functions (\sin, \log, …) ----
    for fn in NAMED_FUNCTIONS:
        expr = re.sub(r'\\' + fn + r'(?=[^a-zA-Z]|$)', fn, expr)

    # ---- \sqrt[n]{...} and \sqrt{...} ----
    expr = re.sub(r'\\sqrt\[([^\]]*)\]\{([^{}]*)\}', r'\2^(1/\1)', expr)
    expr = re.sub(r'\\sqrt\{([^{}]*)\}', r'√(\1)', expr)
    expr = re.sub(r'\\sqrt\s+(\S)', r'√\1', expr)

    # ---- \frac{num}{den} → num/den ----
    # Apply repeatedly because fracs can be nested
    for _ in range(6):
        prev = expr
        expr = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', expr)
        if expr == prev:
            break

    # ---- \dfrac, \tfrac, \cfrac ----
    for _ in range(6):
        prev = expr
        expr = re.sub(r'\\[dct]frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', expr)
        if expr == prev:
            break

    # ---- \binom{n}{k} → C(n,k) ----
    expr = re.sub(r'\\binom\{([^{}]*)\}\{([^{}]*)\}', r'C(\1,\2)', expr)
    expr = re.sub(r'\\dbinom\{([^{}]*)\}\{([^{}]*)\}', r'C(\1,\2)', expr)

    # ---- \overline, \underline, \hat, \tilde, \bar, \vec, \dot, \ddot ----
    for cmd, decoration in (
        (r'\\overline', '̄'), (r'\\underline', ''), (r'\\hat', '̂'),
        (r'\\tilde', '̃'), (r'\\bar', '̄'), (r'\\vec', '⃗'),
        (r'\\dot', '̇'), (r'\\ddot', '̈'), (r'\\breve', '̆'),
        (r'\\check', '̌'), (r'\\acute', '́'), (r'\\grave', '̀'),
        (r'\\widehat', '̂'), (r'\\widetilde', '̃'),
    ):
        expr = re.sub(cmd + r'\{([^{}]*)\}', r'\1' + decoration, expr)
        expr = re.sub(cmd + r'\s+(\S)', r'\1' + decoration, expr)

    # ---- \overset{above}{base} and \underset ----
    expr = re.sub(r'\\overset\{[^{}]*\}\{([^{}]*)\}', r'\1', expr)
    expr = re.sub(r'\\underset\{[^{}]*\}\{([^{}]*)\}', r'\1', expr)

    # ---- \xleftarrow, \xrightarrow ----
    expr = re.sub(r'\\xrightarrow\{[^{}]*\}', '→', expr)
    expr = re.sub(r'\\xleftarrow\{[^{}]*\}', '←', expr)
    expr = re.sub(r'\\xrightarrow\[[^\]]*\]\{[^{}]*\}', '→', expr)

    # ---- limits: \limits_{...}^{...}, \limits^{...}_{...} ----
    expr = re.sub(r'\\limits_\{([^{}]*)\}\^\{([^{}]*)\}', r'(\1 to \2)', expr)
    expr = re.sub(r'\\limits\^\{([^{}]*)\}_\{([^{}]*)\}', r'(\2 to \1)', expr)
    expr = re.sub(r'\\limits_\{([^{}]*)\}', r'(\1)', expr)
    expr = re.sub(r'\\limits\^\{([^{}]*)\}', r'(\1)', expr)
    expr = re.sub(r'\\limits', '', expr)



    # ---- superscripts: ^{...} and ^X ----
    # Multi-char braced superscript → unicode if possible, else parenthesised
    def _sup_braced(m):
        inner = m.group(1)
        converted = _chars_to_sup(inner)
        if converted != inner:          # all chars successfully mapped
            return converted
        return '^(' + inner + ')'      # fallback with parens

    expr = re.sub(r'\^\{([^{}]+)\}', _sup_braced, expr)
    expr = re.sub(r'\^([0-9a-zA-Z])', lambda m: _chars_to_sup(m.group(1)), expr)

    # ---- subscripts: _{...} and _X ----
    def _sub_braced(m):
        inner = m.group(1)
        converted = _chars_to_sub(inner)
        if converted != inner:
            return converted
        return '_(' + inner + ')'      # fallback with parens

    expr = re.sub(r'_\{([^{}]+)\}', _sub_braced, expr)
    expr = re.sub(r'_([0-9a-zA-Z])', lambda m: _chars_to_sub(m.group(1)), expr)

    # ---- Escaped special chars ----
    expr = (expr
            .replace(r'\%', '%')
            .replace(r'\$', '$')
            .replace(r'\&', '&')
            .replace(r'\#', '#')
            .replace(r'\_', '_')
            .replace(r'\{', '(')
            .replace(r'\}', ')')
            .replace(r'\,', ' ')
            .replace(r'\;', ' ')
            .replace(r'\:', ' ')
            .replace(r'\!', '')
            .replace(r'\quad', '  ')
            .replace(r'\qquad', '    ')
            .replace(r'\ ', ' ')
            .replace(r'\left', '')
            .replace(r'\right', '')
            .replace(r'\big', '')
            .replace(r'\Big', '')
            .replace(r'\bigg', '')
            .replace(r'\Bigg', '')
            .replace(r'\middle', '')
            )

    # ---- Strip any remaining bare \command with no argument ----
    expr = re.sub(r'\\[a-zA-Z]+\*?\s*', '', expr)

    # ---- Clean up extra braces left over ----
    expr = re.sub(r'\{([^{}]*)\}', r'\1', expr)
    expr = re.sub(r'\{([^{}]*)\}', r'\1', expr)   # second pass for nesting

    # ---- Collapse excess whitespace ----
    expr = re.sub(r'  +', ' ', expr).strip()

    return expr


def _render_inline_latex(text: str) -> str:
    """
    Replace all $...$ (and $$...$$) spans in *text* with rendered Unicode,
    then strip any remaining naked LaTeX commands outside math mode.
    """
    if not text or '$' not in text and '\\' not in text:
        return text

    # ---- Display math: $$...$$ ----
    def _replace_display(m):
        return _render_latex_expr(m.group(1))

    text = re.sub(r'\$\$(.*?)\$\$', _replace_display, text, flags=re.DOTALL)

    # ---- Inline math: $...$ ----
    def _replace_inline(m):
        return _render_latex_expr(m.group(1))

    text = re.sub(r'\$(.*?)\$', _replace_inline, text, flags=re.DOTALL)

    # ---- Handle any surviving LaTeX-style commands outside math mode ----
    # (e.g. text like "the answer is \frac{1}{2}" without dollar signs)
    if '\\' in text:
        # Apply symbol / greek substitution in text mode too
        for key, val in GREEK.items():
            text = re.sub(re.escape(key) + r'(?=[^a-zA-Z]|$)', val, text)
        for key, val in SYMBOLS.items():
            if not key.startswith(r'\mathbb'):
                text = re.sub(re.escape(key) + r'(?=[^a-zA-Z]|$)', val, text)
        # \frac outside dollars
        for _ in range(4):
            prev = text
            text = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', text)
            if text == prev:
                break
        # \sqrt outside dollars
        text = re.sub(r'\\sqrt\{([^{}]*)\}', r'√(\1)', text)
        # strip leftover commands
        text = re.sub(r'\\[a-zA-Z]+\*?', '', text)
        text = re.sub(r'\{([^{}]*)\}', r'\1', text)
        text = re.sub(r'\{([^{}]*)\}', r'\1', text)

    return text


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def clean(text):
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\x0c", "\\f").replace("\x08", "\\b")
    text = text.replace("\x07", "\\a").replace("\x0b", "\\v")
    text = ILLEGAL_CHARACTERS_RE.sub("", text)
    return _render_inline_latex(text.strip())


def grade_key(raw_grade):
    if not raw_grade:
        return None
    if isinstance(raw_grade, str):
        g = raw_grade.strip().lower().replace(" ", "_")
        return g
    return None


def item_language(item):
    lang = item.get("target_language") or item.get("language")
    if not lang:
        return ""
    return str(lang).strip().lower()


def is_language(item, language):
    return item_language(item) == str(language).strip().lower()


def set_cell_shading(cell, color_hex):
    shading = cell._element.get_or_add_tcPr()
    shd = shading.makeelement(qn("w:shd"), {
        qn("w:val"): "clear",
        qn("w:color"): "auto",
        qn("w:fill"): color_hex,
    })
    shading.append(shd)


def add_paragraph(doc, text, bold=False, italic=False, size=10, color=None,
                  space_before=0, space_after=4, indent=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.left_indent = Inches(indent)
    run = p.add_run(clean(text))
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = "Calibri"
    if color:
        run.font.color.rgb = RGBColor(*color)
    return p


def add_label_value(doc, label, value):
    p = doc.add_paragraph()
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    run_label.font.size = Pt(10)
    run_label.font.name = "Calibri"
    run_label.font.color.rgb = RGBColor(30, 78, 120)
    run_val = p.add_run(clean(value))
    run_val.font.size = Pt(10)
    run_val.font.name = "Calibri"
    return p


def add_dialogue_line(doc, speaker_name, role, text, is_teacher=False):
    p = doc.add_paragraph()
    label = f"{speaker_name} ({role}): "
    run_label = p.add_run(label)
    run_label.bold = True
    run_label.font.size = Pt(10)
    run_label.font.name = "Calibri"
    run_label.font.color.rgb = RGBColor(30, 78, 120) if is_teacher else RGBColor(100, 100, 100)
    run_text = p.add_run(clean(text))
    run_text.font.size = Pt(10)
    run_text.font.name = "Calibri"
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Inches(0.2)
    return p


def add_separator(doc):
    p = doc.add_paragraph()
    run = p.add_run("─" * 80)
    run.font.size = Pt(6)
    run.font.color.rgb = RGBColor(180, 180, 180)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    return p


# ---------------------------------------------------------------------------
# Document construction
# ---------------------------------------------------------------------------

def create_document(title_text, subtitle_text):
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(title_text)
    run.bold = True
    run.font.size = Pt(18)
    run.font.name = "Calibri"
    run.font.color.rgb = RGBColor(30, 78, 120)
    title.paragraph_format.space_after = Pt(8)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(subtitle_text)
    run.font.size = Pt(10)
    run.font.name = "Calibri"
    run.font.color.rgb = RGBColor(100, 100, 100)
    subtitle.paragraph_format.space_after = Pt(12)

    return doc


def render_conversation(doc, conv, index):
    data = conv if 'data' not in conv else conv['data']
    teacher_name = clean(data.get('teacher_name') or conv.get('teacher_name') or 'Teacher')
    student_name = clean(data.get('student_name') or conv.get('student_name') or 'Student')

    add_paragraph(doc, f"Conversation {index}", bold=True, size=11, space_before=8, space_after=4)
    add_label_value(doc, "Teacher Persona", data.get('teacher_persona') or conv.get('teacher_persona') or '')
    # persona_desc = (data.get('persona_blurb') or conv.get('persona_blurb') or 
    #                 data.get('persona_description') or conv.get('persona_description') or
    #                 data.get('teacher_persona_description') or conv.get('teacher_persona_description') or '')
    # add_label_value(doc, "Persona Description", persona_desc)
    add_label_value(doc, "Teacher", f"{teacher_name} ({clean(data.get('teacher_gender') or conv.get('teacher_gender') or '')})")
    add_label_value(doc, "Student", f"{student_name} ({clean(data.get('student_gender') or conv.get('student_gender') or '')})")
    add_paragraph(doc, "", space_after=2)
    add_label_value(doc, "Pre-Scene", data.get('pre_scene') or conv.get('pre_scene') or '')
    add_paragraph(doc, "", space_after=2)
    for turn_num in range(1, 5):
        voice_key = f'teacher_turn_{turn_num}_voice_direction'
        if data.get(voice_key) or conv.get(voice_key):
            add_label_value(doc, f'Voice Direction (Turn {turn_num})',
                            data.get(voice_key) or conv.get(voice_key) or '')
    if data.get('persona_turn2') or conv.get('persona_turn2'):
        add_label_value(doc, 'Persona Instruction (Turn 2)',
                        data.get('persona_turn2') or conv.get('persona_turn2') or '')
    add_paragraph(doc, "", space_after=2)

    dialogue = data.get('dialogue') or conv.get('dialogue')
    if isinstance(dialogue, list):
        try:
            dialogue = sorted(dialogue, key=lambda x: x.get('turn_index', 0))
        except Exception:
            pass
        for turn in dialogue:
            speaker = turn.get('speaker') or turn.get('role') or ''
            text = turn.get('text') or ''
            if speaker and speaker.lower().startswith('teacher'):
                add_dialogue_line(doc, teacher_name, 'Teacher', text, is_teacher=True)
            else:
                add_dialogue_line(doc, student_name, 'Student', text, is_teacher=False)
    else:
        for i in range(1, 5):
            s_text = data.get(f'student{i}') or conv.get(f'student{i}')
            t_text = data.get(f'teacher{i}') or conv.get(f'teacher{i}')
            if s_text:
                add_dialogue_line(doc, student_name, 'Student', s_text, is_teacher=False)
            if t_text:
                add_dialogue_line(doc, teacher_name, 'Teacher', t_text, is_teacher=True)

    add_paragraph(doc, "", space_after=2)
    add_label_value(doc, "Post-Scene", data.get('post_scene') or conv.get('post_scene') or '')
    add_separator(doc)


def build_persona_documents(input_file, output_dir, language=DEFAULT_LANGUAGE, version=None, set_number=SET_NUMBER, start_id=None, end_id=None, task_ids=None, chunk_size=None, personas_to_process=None, persona_start_sets=None):
    language_key = str(language).strip().lower()
    if not language_key:
        raise ValueError("Language must be provided")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Gather input files (supporting both file and directory)
    if os.path.isdir(input_file):
        jsonl_files = []
        for root, _, files in os.walk(input_file):
            for file in sorted(files):
                if file.endswith('.jsonl'):
                    jsonl_files.append(os.path.join(root, file))
    else:
        jsonl_files = [input_file]

    # Parse task IDs set if provided as a string
    task_ids_set = parse_task_ids(task_ids) if isinstance(task_ids, str) else task_ids

    # Filter files by task/test ID if specified
    if start_id is not None or end_id is not None or task_ids_set is not None:
        jsonl_files = [f for f in jsonl_files if matches_task_id(f, start_id, end_id, task_ids_set)]
        print(f"Applying task ID filters: found {len(jsonl_files)} matching file(s).")

    # Filter files by version if specified
    if version:
        jsonl_files = [f for f in jsonl_files if matches_version(f, version)]
        print(f"Applying version filter '{version}': found {len(jsonl_files)} matching file(s).")

    all_conversations = []
    seen_ids = set()

    for file_path in jsonl_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not is_language(item, language_key):
                    continue
                raw_grade = None
                if isinstance(item, dict):
                    cell = item.get('cell')
                    if isinstance(cell, dict):
                        raw_grade = cell.get('grade_bucket')
                    if raw_grade is None:
                        raw_grade = item.get('grade_bucket')
                grade = grade_key(raw_grade)
                if grade not in ALLOWED_GRADES:
                    continue
                persona = (item.get('teacher_persona') or item.get('persona') or '').strip()
                if persona not in PERSONA_ORDER:
                    continue
                
                # Deduplicate by item ID
                item_id = item.get('id')
                if item_id:
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)

                all_conversations.append((grade, persona, item))

    by_persona = defaultdict(list)
    for grade, persona, item in all_conversations:
        by_persona[persona].append((grade, item))

    os.makedirs(output_dir, exist_ok=True)
    written_files = []

    language_title = language_key.replace('_', ' ').title()
    for persona in PERSONA_ORDER:
        # Only process requested personas if personas_to_process is specified
        if personas_to_process is not None and persona not in personas_to_process:
            continue

        items = by_persona.get(persona, [])
        if not items:
            continue

        # Set the starting set number based on the persona mapping, or default to set_number
        if persona_start_sets and persona in persona_start_sets:
            start_set = persona_start_sets[persona]
        else:
            start_set = set_number

        # Sort all items by grade so that the chunked documents remain grouped by grade
        items.sort(key=lambda x: (x[0],))

        # Chunk items into sublists of at most chunk_size conversations
        if chunk_size:
            chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        else:
            chunks = [items]

        for chunk_idx, chunk in enumerate(chunks):
            current_set_number = start_set + chunk_idx

            unique_grades = sorted(list(set(g for g, item in chunk)))
            
            # Format name like Language_Persona_Set{n}.docx
            lang_title = language_key.replace('_', ' ').title().replace(' ', '_')
            persona_title = persona.title()
            filename = f"{lang_title}_{persona_title}_Set{current_set_number}.docx"
            output_path = os.path.join(output_dir, filename)
            
            grades_title_list = [GRADE_DISPLAY.get(g, g.replace("_", " ").title()) for g in unique_grades]
            grades_title = " + ".join(grades_title_list)
            
            doc = create_document(
                f"{language_title} Conversations — {grades_title} — {persona}",
                f"Filtered {language_title} conversations: {grades_title}"
            )

            conversation_index = 0
            for grade, item in chunk:
                conversation_index += 1
                heading = doc.add_heading(level=2)
                heading_run = heading.add_run(f"📚 {GRADE_DISPLAY.get(grade, grade.title())}")
                heading_run.font.name = "Calibri"
                heading_run.font.size = Pt(13)
                heading_run.font.bold = True
                heading_run.font.color.rgb = RGBColor(30, 78, 120)
                heading.paragraph_format.space_before = Pt(10)
                heading.paragraph_format.space_after = Pt(6)
                render_conversation(doc, item, conversation_index)

            doc.save(output_path)
            written_files.append((persona, output_path, len(chunk)))

    return written_files


def infer_language_from_path(input_file):
    filename = os.path.basename(input_file).lower()
    for lang in ('english', 'hindi', 'kannada', 'marathi', 'odia', 'tamil', 'telugu', 'gujarati'):
        if lang in filename:
            return lang
    return None


def infer_language_from_file(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            lang = item.get('target_language') or item.get('language')
            if lang:
                return str(lang).strip().lower()
    return None


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate persona DOCX files from conversation JSONL input for a given language."
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default='conversations_final.jsonl',
        help='Path to the input JSONL file or directory (default: conversations_final.jsonl)'
    )
    parser.add_argument(
        'output_dir',
        nargs='?',
        default=None,
        help='Directory to write the generated DOCX files (default: <language>_persona_docx)'
    )
    parser.add_argument(
        '--output-dir',
        '-o',
        dest='output_dir',
        default=None,
        help='Directory to write the generated DOCX files (default: <language>_persona_docx)'
    )
    parser.add_argument(
        '--language',
        '-l',
        default=None,
        help='Target language to filter conversations (default: inferred from input file or english)'
    )
    parser.add_argument(
        '--version',
        '-v',
        default=None,
        help='Filter conversation task files by version (e.g. 3, version_3, new_version)'
    )
    parser.add_argument(
        '--set',
        '-s',
        default=None,
        type=int,
        help='Set number to append to the filename (defaults to SET_NUMBER at top of script)'
    )
    parser.add_argument(
        '--start-id',
        default=None,
        type=int,
        help='Starting task ID to filter files (inclusive)'
    )
    parser.add_argument(
        '--end-id',
        default=None,
        type=int,
        help='Ending task ID to filter files (inclusive)'
    )
    parser.add_argument(
        '--task-ids',
        '-t',
        default=None,
        help='Comma-separated list or range of task IDs (e.g. 20179-20186 or 20179,20180)'
    )
    parser.add_argument(
        '--audit',
        action='store_true',
        help='Audit an output directory for any leftover raw LaTeX after DOCX generation'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=None,
        help='Maximum number of conversations per document (default: no chunking)'
    )
    parser.add_argument(
        '--personas',
        default=None,
        help='Comma-separated list of personas to process (default: all)'
    )
    parser.add_argument(
        '--persona-start-sets',
        default=None,
        help='Comma-separated mapping of persona starting sets (e.g. calm_explainer=7,storyteller=4)'
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.audit:
        audit_dir = args.output_dir or f"{(args.language or DEFAULT_LANGUAGE).strip().lower()}_persona_docx"
        audit_docx_dir(audit_dir)
        return

    language = args.language
    if not language:
        if os.path.isdir(args.input_file):
            language = DEFAULT_LANGUAGE
        else:
            language = infer_language_from_path(args.input_file) or infer_language_from_file(args.input_file) or DEFAULT_LANGUAGE
        print(f"Inferred language '{language}' from input source")

    output_dir = args.output_dir or f"{language.strip().lower()}_persona_docx"
    
    set_num = args.set if args.set is not None else SET_NUMBER

    # Parse persona start sets
    persona_start_sets = {}
    if args.persona_start_sets:
        for part in args.persona_start_sets.split(','):
            if '=' in part:
                p, s = part.split('=', 1)
                persona_start_sets[p.strip().lower()] = int(s.strip())

    # Parse personas to process list
    personas_to_process = None
    if args.personas:
        personas_to_process = [p.strip().lower() for p in args.personas.split(',')]
    
    try:
        results = build_persona_documents(
            input_file=args.input_file, 
            output_dir=output_dir, 
            language=language,
            version=args.version,
            set_number=set_num,
            start_id=args.start_id,
            end_id=args.end_id,
            task_ids=args.task_ids,
            chunk_size=args.chunk_size,
            personas_to_process=personas_to_process,
            persona_start_sets=persona_start_sets
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if not results:
        print(
            f"No {language.title()} conversations found for the allowed grades."
        )
        return

    print("Generated persona DOCX files:")
    for persona, path, count in results:
        print(f" - {persona}: {path} ({count} conversations)")

    try:
        from update_status_report import update_status
        update_status()
    except Exception as e:
        print(f"Warning: Could not auto-update status report: {e}")


# ---------------------------------------------------------------------------
# Audit mode: scan generated docx files for surviving raw LaTeX
# Usage: python generate_persona_docs.py --audit english_persona_docx/
# ---------------------------------------------------------------------------

RAW_LATEX_RE = re.compile(
    r'(?:'
    r'\$[^$]{1,200}\$'     # unconverted $...$
    r'|\\[a-zA-Z]+\*?'     # any surviving \command
    r'|\\\{'               # \{
    r'|\\\}'               # \}
    r')'
)


def audit_docx_dir(directory):
    import glob

    files = sorted(glob.glob(os.path.join(directory, '*.docx')))
    if not files:
        print(f"No .docx files found in {directory!r}")
        return

    total_hits = 0
    for path in files:
        doc = Document(path)
        hits_in_file = []
        for para in doc.paragraphs:
            text = para.text
            matches = RAW_LATEX_RE.findall(text)
            if matches:
                hits_in_file.append((text[:120], matches))
        if hits_in_file:
            print(f"\n❌  {os.path.basename(path)} — {len(hits_in_file)} paragraph(s) with raw LaTeX:")
            for ctx, matches in hits_in_file[:10]:
                print(f"      context : {ctx!r}")
                print(f"      matches : {matches}")
            if len(hits_in_file) > 10:
                print(f"      ... and {len(hits_in_file)-10} more")
            total_hits += len(hits_in_file)
        else:
            print(f"✓  {os.path.basename(path)}")

    print(f"\n{'All clean!' if total_hits == 0 else f'{total_hits} total paragraphs with raw LaTeX found.'}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--audit':
        audit_dir = sys.argv[2] if len(sys.argv) > 2 else 'english_persona_docx'
        audit_docx_dir(audit_dir)
    else:
        main()