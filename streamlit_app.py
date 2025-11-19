import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
from pathlib import Path
import sympy as sp
import re

st.set_page_config(page_title="함수 절댓값 시각화", layout="wide")

# 로컬 폰트 등록 (프로젝트의 `font/NanumGothic-Regular.ttf` 사용)
# 존재하면 matplotlib에 추가하고 전체 폰트로 설정합니다.
try:
    font_path = Path(__file__).resolve().parent / "font" / "NanumGothic-Regular.ttf"
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        fp = fm.FontProperties(fname=str(font_path))
        plt.rcParams['font.family'] = fp.get_name()
        # 한글 폰트로 인해 마이너스 기호가 깨질 수 있으므로 대체 처리
        plt.rcParams['axes.unicode_minus'] = False
    else:
        # 폰트 파일이 없으면 무시
        pass
except Exception:
    # 폰트 설정에 실패해도 앱 동작을 멈추지 않음
    pass

# 사이드바에서 함수 입력
with st.sidebar:
    st.header("📝 함수 설정")
    st.write("최대 이차함수의 절댓값을 실수 전체에 적용합니다.")
    function_input = st.text_input(
        "함수를 입력하세요",
        value="x^2 - 2x - 3",
        help=("예: 4x^2+2x+2 또는 x^2-2x-3. \n"
              "제곱은 반드시 '^'으로 표기하세요 (예: x^2). \n"
              "변수는 소문자 'x'만 허용합니다. 한글 입력은 허용되지 않습니다.")
    )

# 함수 파싱 및 검증
x = sp.Symbol('x')

def normalize_abs_notation(s: str) -> str:
    """입력 문자열에서 여러 절댓값 표기(Abs, abs, |...|)를 SymPy가 이해하는 'Abs(...)'로 정규화합니다.
    '|' 표기는 짝을 이뤄야 하며, 짝이 맞지 않으면 에러를 발생시킵니다.
    """
    if not isinstance(s, str):
        return s
    # 소문자 abs(...) -> Abs(...)
    s = s.replace('abs(', 'Abs(')
    s = s.replace('ABS(', 'Abs(')

    # '|' 표기를 Abs(...)로 변환: 짝수 개의 '|'이어야 함
    if '|' in s:
        out = []
        open_stack = 0
        for ch in s:
            if ch == '|':
                if open_stack % 2 == 0:
                    out.append('Abs(')
                else:
                    out.append(')')
                open_stack += 1
            else:
                out.append(ch)
        if open_stack % 2 != 0:
            # 짝이 맞지 않음
            raise ValueError("'|' 표기의 짝이 맞지 않습니다. 예: |x-1|")
        s = ''.join(out)
    return s


def enforce_ascii_math(s: str) -> str:
    """입력 문자열을 엄격한 ASCII 수식 표기로 정리합니다.

    규칙 요약:
      - 한글 입력을 허용하지 않습니다.
      - 제곱 표기는 '^'만 허용합니다 (예: x^2). '**'는 사용할 수 없습니다.
      - 변수는 소문자 'x'만 허용합니다. 'abs(...)'와 '|' 표기는 허용합니다.
      - 숫자와 'x' 사이의 암묵적 곱(예: 4x)을 명시적 곱('4*x')으로 변환합니다.
      - 최종적으로 SymPy로 전달하기 위해 '^'를 '**'로 변환합니다.
    """
    if not isinstance(s, str):
        return s
    t = s.strip()

    # 한글 포함 여부 검사 (허용하지 않음)
    if re.search(r'[\uac00-\ud7a3]', t):
        raise ValueError("한글 입력은 허용되지 않습니다. 수식은 ASCII 형식으로 입력하세요 (예: 4x^2+2x+2).")

    # '**' 사용 금지 (사용자에게 '^' 사용을 강제)
    if '**' in t:
        raise ValueError("제곱 표기는 '^'을 사용하세요. 예: x^2")

    # 알파벳 토큰 검사: 허용되는 단어만 ('x', 'abs')
    for word in re.findall(r'[A-Za-z]+', t):
        if word.lower() not in ('x', 'abs'):
            raise ValueError(f"허용되지 않는 식별자 '{word}'가 있습니다. 변수는 'x'만 사용하세요.")

    # 대문자 X -> 소문자 x
    t = t.replace('X', 'x')

    # 숫자 또는 닫는 괄호 뒤에 오는 x에 대해서 명시적 곱으로 변경: '4x' -> '4*x', ')x' -> ')*x'
    t = re.sub(r'(\d)\s*(?=x)', r"\1*", t)
    t = re.sub(r'\)\s*(?=x)', r')*', t)
    # x 다음에 '('가 오면 곱으로 해석: 'x(' -> 'x*('
    t = re.sub(r'x\s*(?=\()', r'x*', t)

    # 허용되지 않은 문자가 있는지 간단 검사
    if not re.match(r"^[0-9xX+\-*/^\.()\|A-Za-z\s]*$", t):
        raise ValueError("허용되지 않는 문자가 포함되어 있습니다. 수식은 숫자, 연산자, 'x', '^', 'abs', '|' 만 사용하세요.")

    # SymPy용: '^' -> '**'
    t = t.replace('^', '**')

    # 'ABS(' 같은 케이스를 소문자 abs로 정리 (normalize_abs_notation에서 대문자 처리 예정)
    t = t.replace('ABS(', 'abs(')

    return t


def remove_abs(expr):
    """Expression tree에서 Abs를 제거한 새 표현을 반환합니다 (차수 판정용).
    예: Abs(x-1)**2 -> (x-1)**2
    """
    if expr is None:
        return expr
    if isinstance(expr, sp.Abs):
        return remove_abs(expr.args[0])
    if not expr.args:
        return expr
    return expr.func(*[remove_abs(a) for a in expr.args])


try:
    # ASCII 수식 전처리 -> 절댓값 표기 정규화 -> sympify
    pre = enforce_ascii_math(function_input)
    normalized = normalize_abs_notation(pre)
    f_expr = sp.sympify(normalized)

    # 상수함수 처리(명시적)
    if not f_expr.has(x) and f_expr.is_number:
        f_expr = sp.sympify(normalized)

    # 다항식 차수 확인: Abs를 제거한 표현으로 판단
    try:
        poly_candidate = remove_abs(f_expr)
        poly = sp.Poly(sp.expand(poly_candidate), x)
        degree = poly.degree()
    except Exception:
        # Poly 변환이 안 되면 안전하게 2보다 큰 것으로 처리하지 않음
        # (예: 비다항식 형태) 이 경우 degree를 0으로 설정하여 이후 검증으로 걸러지게 함
        degree = 0

    if degree > 2:
        st.error("⚠️ 2차 이하의 함수만 입력 가능합니다!")
        st.stop()
except ValueError as e:
    st.error(f"⚠️ 함수 입력 오류: {e}")
    st.stop()
except Exception:
    st.error("⚠️ 유효한 함수를 입력해주세요!")
    st.stop()

# 절댓값 타입 선택 상태 관리
if 'abs_type' not in st.session_state:
    st.session_state.abs_type = 'f(x)'
if 'abs_history' not in st.session_state:
    st.session_state.abs_history = []
if 'current_expr' not in st.session_state:
    st.session_state.current_expr = function_input

# 메인 제목
st.title("📊 함수의 절댓값 시각화 (누적 계산기)")

st.write("**계산기처럼 절댓값을 누적으로 적용하세요!**")

# 절댓값 타입 선택 버튼 (누적 적용)
col_btn1, col_btn2, col_btn3, col_reset = st.columns([1, 1, 1, 0.8])

with col_btn1:
    if st.button("📌 |f(x)|", use_container_width=True, key="btn_fy"):
        st.session_state.abs_history.append('|f(x)|')
        st.session_state.abs_type = 'f(x)'

with col_btn2:
    if st.button("📌 f(|x|)", use_container_width=True, key="btn_fx"):
        st.session_state.abs_history.append('f(|x|)')
        st.session_state.abs_type = 'x'

with col_btn3:
    if st.button("📌 |y|", use_container_width=True, key="btn_y"):
        st.session_state.abs_history.append('|y|')
        st.session_state.abs_type = 'y'

with col_reset:
    if st.button("🔄 초기화", use_container_width=True, key="btn_reset"):
        st.session_state.abs_history = []
        st.session_state.current_expr = function_input
        st.rerun()

st.write("---")

# 적용 내역 표시
st.header("📝 적용 내역")

if st.session_state.abs_history:
    col_history_left, col_history_right = st.columns([2, 1])
    
    with col_history_left:
        history_text = " → ".join(st.session_state.abs_history)
        st.write(f"**적용된 절댓값 순서:** {history_text}")
    
    with col_history_right:
        st.write(f"**총 {len(st.session_state.abs_history)}회 적용**")
else:
    st.info("⏳ 아직 절댓값이 적용되지 않았습니다. 버튼을 눌러보세요!")

st.write("---")

# 메인 콘텐츠
col_main_left, col_main_right = st.columns([1, 3])

with col_main_left:
    st.header("📋 정보")
    st.write(f"**원본 함수: y = {function_input}**")
    st.write(f"**차수: {degree}차**")
    st.write(f"**구간: ℝ (실수 전체)**")
    
    st.write("---")
    
    if st.session_state.abs_history:
        last_mode = st.session_state.abs_type
        if last_mode == 'f(x)':
            st.write("**마지막 적용: |f(x)|**")
            st.write("y축에 절댓값 적용")
        elif last_mode == 'x':
            st.write("**마지막 적용: f(|x|)**")
            st.write("x축에 절댓값 적용")
        else:  # 'y'
            st.write("**마지막 적용: |y|**")
            st.write("y값 전체에 절댓값 적용")
    else:
        st.write("**상태: 원본 함수**")
        st.write("아직 절댓값이 적용되지 않았습니다.")

with col_main_right:
    st.header("📈 그래프")
    
    # 함수 정의
    def f(val):
        """원본 함수"""
        try:
            return float(f_expr.subs(x, val))
        except:
            return np.nan

    def f_abs_fy(val):
        """y축에 절댓값을 씌운 함수"""
        return abs(f(val))
    
    def f_abs_fx(val):
        """x축에 절댓값을 씌운 함수"""
        return f(abs(val))
    
    def f_abs_y(val):
        """전체 y값에 절댓값을 씌운 함수"""
        return abs(f(val))

    # 그래프 그리기
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

    # X축 범위 설정
    x_vals = np.linspace(-10, 10, 500)

    # 원본 함수
    y_orig = np.array([f(val) for val in x_vals])

    # sympy로 누적된 연산을 적용하여 최종 심볼릭 표현과 숫자 배열 생성
    sym_final = f_expr
    for op in st.session_state.abs_history:
        if op == 'f(|x|)':
            sym_final = sym_final.subs(x, sp.Abs(x))
        else:  # '|f(x)|' 또는 '|y|'는 동일하게 y에 절댓값 적용
            sym_final = sp.Abs(sym_final)

    # 라벨과 제목 설정
    if st.session_state.abs_history:
        last_op = st.session_state.abs_history[-1]
        if last_op == 'f(|x|)':
            title_suffix = "f(|x|) 포함 변환"
            ylabel = "f(|x|) / 변환 결과"
        elif last_op == '|f(x)|' or last_op == '|y|':
            title_suffix = "절댓값 적용 결과"
            ylabel = "|...|"
        else:
            title_suffix = "변환 결과"
            ylabel = "y"
    else:
        title_suffix = "변환 없음"
        ylabel = "f(x)"

    # sympy 표현을 숫자 함수로 변환 (안전하게)
    try:
        numeric_func = sp.lambdify(x, sym_final, modules=["numpy"])
        y_transformed = numeric_func(x_vals)
        # lambdify 결과가 스칼라인 경우 처리
        y_transformed = np.array(y_transformed, dtype=float)
    except Exception:
        # 실패하면 원본으로 되돌림
        y_transformed = y_orig
        title_suffix = "변환 오류 - 원본 표시"
        ylabel = "f(x)"

    # 첫 번째 그래프: 원본 함수
    ax1.plot(x_vals, y_orig, 'b-', linewidth=2.5, label='원본 함수')
    ax1.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
    ax1.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlabel('x', fontsize=12)
    ax1.set_ylabel('f(x)', fontsize=12)
    ax1.set_title(f'원본 함수: y = {function_input}', fontsize=12, fontweight='bold')
    ax1.set_ylim(-15, 15)
    ax1.legend(fontsize=10)

    # 이차함수이면 꼭짓점 좌표를 계산해서 그래프 상에 (a,b) 형태로 표시합니다.
    try:
        if degree == 2:
            p = sp.Poly(f_expr, x)
            # 계수 추출: a, b (a != 0)
            # Poly.coeffs()는 최고차항부터 반환하므로 안전하게 사용
            coeffs = p.coeffs()
            if len(coeffs) >= 3:
                a_coeff = float(coeffs[0])
                b_coeff = float(coeffs[1])
            else:
                # 안전한 폴백
                a_coeff = float(p.coeff_monomial(x**2))
                b_coeff = float(p.coeff_monomial(x))

            xv = -b_coeff / (2 * a_coeff)
            yv = float(f_expr.subs(x, xv))

            # 숫자 포맷: 정수에 가까우면 정수로, 아니면 소수 둘째자리까지 표시
            def fmt_num(v):
                try:
                    if abs(v - round(v)) < 1e-9:
                        return str(int(round(v)))
                except Exception:
                    pass
                s = f"{v:.2f}"
                if '.' in s:
                    s = s.rstrip('0').rstrip('.')
                return s

            # y 표시 위치를 위 또는 아래로 결정 (약간의 여백 포함)
            y_min, y_max = ax1.get_ylim()
            y_range = y_max - y_min if (y_max - y_min) != 0 else 1.0
            offset = 0.06 * y_range

            # 기본은 꼭짓점 위에 표시, 위로 표시하면 영역을 벗어나면 아래에 표시
            if yv + offset <= y_max - 0.02 * y_range:
                text_y = yv + offset
            else:
                text_y = yv - offset

            ax1.scatter([xv], [yv], color='orange', zorder=5)
            label = f'({fmt_num(xv)}, {fmt_num(yv)})'
            ax1.annotate(label, xy=(xv, yv), xytext=(xv, text_y),
                         ha='center', fontsize=10,
                         bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8))
    except Exception:
        # 표시가 실패해도 앱은 계속 동작해야 함
        pass

    # 두 번째 그래프: 절댓값을 씌운 함수
    ax2.plot(x_vals, y_transformed, 'r-', linewidth=2.5, label=f'{ylabel}')
    ax2.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
    ax2.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlabel('x', fontsize=12)
    ax2.set_ylabel(ylabel, fontsize=12)
    ax2.set_title(f'절댓값 적용: {title_suffix}', fontsize=12, fontweight='bold')
    ax2.set_ylim(-15, 15)
    ax2.legend(fontsize=10)

    plt.tight_layout()
    st.pyplot(fig)

# 최종 수식 표시
st.write("---")
st.header("✨ 최종 결과")

if st.session_state.abs_history:
    col_formula1, col_formula2 = st.columns([1, 1])
    
    with col_formula1:
        st.subheader("📋 적용 과정")
        st.write(f"**Step 0 (원본):** y = {function_input}")
        
        for i, operation in enumerate(st.session_state.abs_history, 1):
            if operation == '|f(x)|':
                st.write(f"**Step {i}:** y축에 절댓값 → |y| = |f(x)|")
            elif operation == 'f(|x|)':
                st.write(f"**Step {i}:** x축에 절댓값 → y = f(|x|)")
            elif operation == '|y|':
                st.write(f"**Step {i}:** 전체 y값에 절댓값 → |y|")
    
    with col_formula2:
        st.subheader("🎯 최종 함수")

        # sympy로 최종식을 구성해서 왼쪽에 y를 둔 등식으로 보여줍니다.
        if len(st.session_state.abs_history) > 0:
            sym_final_display = f_expr
            for op in st.session_state.abs_history:
                if op == 'f(|x|)':
                    sym_final_display = sym_final_display.subs(x, sp.Abs(x))
                else:
                    sym_final_display = sp.Abs(sym_final_display)

            try:
                eq2 = sp.Eq(sp.Symbol('y'), sp.simplify(sym_final_display))
                st.latex(sp.latex(eq2))
            except Exception:
                st.write(f"y = {str(sym_final_display)}")
            st.info("위 수식은 누적 적용된 절댓값 연산의 최종 결과입니다.")
else:
    st.info("절댓값을 누적 적용하면 최종 함수식이 표시됩니다.")

st.write("---")

# 함수값 비교 표
st.header("🔍 함수값 비교")

abs_type = st.session_state.abs_type if st.session_state.abs_history else 'original'
test_points = np.linspace(-5, 5, 11)

if abs_type == 'original':
    data_dict = {
        'x': [round(val, 2) for val in test_points],
        'f(x)': [round(f(val), 2) for val in test_points]
    }
    st.write("**상태: 원본 함수**")
elif abs_type == 'f(x)':
    data_dict = {
        'x': [round(val, 2) for val in test_points],
        'f(x)': [round(f(val), 2) for val in test_points],
        '|f(x)|': [round(abs(f(val)), 2) for val in test_points]
    }
    st.write("**마지막 적용: |f(x)| (y축에 절댓값)**")
elif abs_type == 'x':
    data_dict = {
        'x': [round(val, 2) for val in test_points],
        'f(x)': [round(f(val), 2) for val in test_points],
        'f(|x|)': [round(f(abs(val)), 2) for val in test_points]
    }
    st.write("**마지막 적용: f(|x|) (x축에 절댓값)**")
else:  # 'y'
    data_dict = {
        'x': [round(val, 2) for val in test_points],
        'f(x)': [round(f(val), 2) for val in test_points],
        '|y|': [round(abs(f(val)), 2) for val in test_points]
    }
    st.write("**마지막 적용: |y| (전체 y값에 절댓값)**")

st.dataframe(data_dict, use_container_width=True)