import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from pathlib import Path
import sympy as sp
import re

st.set_page_config(page_title="함수 절댓값 시각화", layout="wide")

# 로컬 폰트 등록: 프로젝트 내 `fonts/` 폴더에서 나눔고딕 ttf를 찾아 matplotlib에 추가합니다.
try:
    base_dir = Path(__file__).resolve().parent
    candidate_paths = [
        base_dir / 'fonts',
        base_dir / 'font',
        base_dir / 'fonts' / 'Nanum_Gothic'
    ]

    font_file = None
    # 우선적으로 흔한 파일명을 찾고, 없으면 폴더 내에서 Nanum으로 시작하는 ttf를 찾음
    preferred_names = ['NanumGothic-Regular.ttf', 'NanumGothuic-Regular.ttf', 'NanumGothic.ttf']
    for p in candidate_paths:
        try:
            if not p.exists():
                continue
        except Exception:
            continue
        for name in preferred_names:
            candidate = p / name
            if candidate.exists():
                font_file = candidate
                break
        if font_file:
            break
        # 글꼴 파일을 glob으로 찾아보기
        for candidate in p.glob('*Nanum*.ttf'):
            if candidate.is_file():
                font_file = candidate
                break
        if font_file:
            break

    if font_file is not None:
        fm.fontManager.addfont(str(font_file))
        fp = fm.FontProperties(fname=str(font_file))
        # matplotlib 설정: 폰트 이름을 사용하여 기본 패밀리와 sans-serif에 우선 적용
        try:
            font_name = fp.get_name()
            plt.rcParams['font.family'] = font_name
            plt.rcParams['font.sans-serif'] = [font_name]
        except Exception:
            # 실패하더라도 앱이 멈추지 않도록 무시
            pass
        # 한글 폰트로 인해 마이너스 기호가 깨질 수 있으므로 대체 처리
        plt.rcParams['axes.unicode_minus'] = False
    else:
        # 폰트 파일을 찾지 못하면 무시
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
st.title("절댓값이 있는 함수의 그래프 이해하기")

st.write("**계산기처럼 절댓값을 누적으로 적용하세요!**")

# 메인 콘텐츠: 왼쪽은 그래프(넓게), 오른쪽은 정보+버튼(좁게)
col_main_left, col_main_right = st.columns([3, 1])

with col_main_right:
    st.header("📋 정보")
    st.write(f"**원본 함수: y = {function_input}**")
    st.write(f"**차수: {degree}차**")
    st.write(f"**구간: ℝ (실수 전체)**")
    
    st.write("---")
    
    # 오른쪽 칼럼에 절댓값 적용 버튼을 수직으로 배치합니다 (버튼을 먼저 렌더링하여
    # 클릭 시 즉시 아래 수식 표시에 반영되도록 함).
    st.subheader("절댓값 적용 (누적)")
    if st.button("📌 |f(x)|", key="btn_fy_right"):
        st.session_state.abs_history.append('|f(x)|')
        st.session_state.abs_type = 'f(x)'

    if st.button("📌 f(|x|)", key="btn_fx_right"):
        st.session_state.abs_history.append('f(|x|)')
        st.session_state.abs_type = 'x'

    if st.button("📌 |y|", key="btn_y_right"):
        st.session_state.abs_history.append('|y|')
        st.session_state.abs_type = 'y'

    if st.button("🔄 초기화", key="btn_reset_right"):
        st.session_state.abs_history = []
        st.session_state.current_expr = function_input

    # 현재 함수식에 절댓값이 어떻게 적용되었는지 수식으로 표시합니다.
    try:
        sym_final_display = f_expr
        left_abs_display = False
        for op in st.session_state.abs_history:
            if op == 'f(|x|)':
                sym_final_display = sym_final_display.subs(x, sp.Abs(x))
            elif op == '|f(x)|':
                sym_final_display = sp.Abs(sym_final_display)
            elif op == '|y|':
                left_abs_display = True

        try:
            if left_abs_display:
                eq_disp = sp.Eq(sp.Abs(sp.Symbol('y')), sp.simplify(sym_final_display))
            else:
                eq_disp = sp.Eq(sp.Symbol('y'), sp.simplify(sym_final_display))
            st.subheader("🔣 현재 적용된 수식")
            st.latex(sp.latex(eq_disp))
        except Exception:
            st.subheader("🔣 현재 적용된 수식")
            if left_abs_display:
                st.write(f"|y| = {str(sym_final_display)}")
            else:
                st.write(f"y = {str(sym_final_display)}")

    except Exception:
        st.write("적용된 수식을 표시할 수 없습니다.")

    # (버튼 블록은 위로 이동되어 중복 제거됨)
with col_main_left:
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

    # 그래프 그리기 (Plotly 사용하여 마우스 오버로 x절편 좌표 표시)
    x_vals = np.linspace(-10, 10, 1000)

    # 원본 함수
    y_orig = np.array([f(val) for val in x_vals], dtype=float)

    # sympy로 누적된 연산을 적용하여 최종 심볼릭 표현과 숫자 배열 생성
    # 주의: '|y|'는 좌변 절댓값을 의미하므로 sym_final에는 Abs를 적용하지 않고
    # 별도 flag(left_abs)를 사용하여 그래프를 그립니다.
    sym_final = f_expr
    left_abs = False
    for op in st.session_state.abs_history:
        if op == 'f(|x|)':
            sym_final = sym_final.subs(x, sp.Abs(x))
        elif op == '|f(x)|':
            sym_final = sp.Abs(sym_final)
        elif op == '|y|':
            # 좌변 절댓값 표기: sym_final은 그대로 두고 플래그만 설정
            left_abs = True

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
        y_transformed = np.array(y_transformed, dtype=float)
    except Exception:
        y_transformed = y_orig
        title_suffix = "변환 오류 - 원본 표시"
        ylabel = "f(x)"

    # x절편(근) 계산: 선형 보간으로 위치 계산 (sign change 기반)
    def find_roots(xs, ys):
        roots = []
        ys = np.array(ys, dtype=float)
        finite_mask = np.isfinite(ys)
        xs = np.array(xs)
        for i in range(len(ys) - 1):
            if not (finite_mask[i] and finite_mask[i+1]):
                continue
            y1, y2 = ys[i], ys[i+1]
            if abs(y1) < 1e-8:
                roots.append(xs[i])
            if y1 == 0 or y2 == 0:
                # handled by abs check or next iteration
                pass
            if y1 * y2 < 0:
                x1, x2 = xs[i], xs[i+1]
                # linear interpolation
                xr = x1 - y1 * (x2 - x1) / (y2 - y1)
                roots.append(xr)
        return sorted(set([round(r, 8) for r in roots]))

    roots_orig = find_roots(x_vals, y_orig)
    roots_trans = find_roots(x_vals, y_transformed)

    # Plotly subplot
    fig = make_subplots(rows=1, cols=2, subplot_titles=(f'원본 함수: y = {function_input}', f'절댓값 적용: {title_suffix}'))

    # 원본 함수 선
    fig.add_trace(go.Scatter(x=x_vals, y=y_orig, mode='lines', name='원본 함수', line=dict(color='blue')),
                  row=1, col=1)
    # x축
    fig.add_trace(go.Scatter(x=[x_vals[0], x_vals[-1]], y=[0, 0], mode='lines', line=dict(color='black', width=1), showlegend=False), row=1, col=1)

    # 꼭짓점 표시 (이차함수인 경우)
    try:
        if degree == 2:
            p = sp.Poly(f_expr, x)
            coeffs = p.coeffs()
            if len(coeffs) >= 3:
                a_coeff = float(coeffs[0])
                b_coeff = float(coeffs[1])
            else:
                a_coeff = float(p.coeff_monomial(x**2))
                b_coeff = float(p.coeff_monomial(x))
            xv = -b_coeff / (2 * a_coeff)
            yv = float(f_expr.subs(x, xv))
            fig.add_trace(go.Scatter(x=[xv], y=[yv], mode='markers', marker=dict(color='orange', size=10), name='꼭짓점'), row=1, col=1)
            fig.add_annotation(x=xv, y=yv, text=f'({round(xv,3)}, {round(yv,3)})', showarrow=True, arrowhead=1, ax=0, ay=-30, row=1, col=1)
    except Exception:
        pass

    # 원본 함수의 x절편 마커 (호버로 좌표 표시)
    if roots_orig:
        fig.add_trace(go.Scatter(x=roots_orig, y=[0]*len(roots_orig), mode='markers', marker=dict(color='red', size=8),
                                 hovertemplate='x=%{x:.4f}<br>y=0', name='x절편'), row=1, col=1)

    # 변환 함수 그리기: left_abs 플래그가 있으면 |y| = f(x) 형태로 그립니다.
    if left_abs:
        # y_transformed은 f(x) 값. |y| = f(x) 이면 f(x) >= 0 인 구간에서 y = ±f(x)
        y_vals = y_transformed
        y_pos = np.where(np.isfinite(y_vals) & (y_vals >= 0), y_vals, np.nan)
        y_neg = np.where(np.isfinite(y_vals) & (y_vals >= 0), -y_vals, np.nan)
        fig.add_trace(go.Scatter(x=x_vals, y=y_pos, mode='lines', name='y = +f(x) (조건 f>=0)', line=dict(color='red')),
                      row=1, col=2)
        fig.add_trace(go.Scatter(x=x_vals, y=y_neg, mode='lines', name='y = -f(x) (조건 f>=0)', line=dict(color='purple', dash='dash')),
                      row=1, col=2)
        fig.add_trace(go.Scatter(x=[x_vals[0], x_vals[-1]], y=[0, 0], mode='lines', line=dict(color='black', width=1), showlegend=False), row=1, col=2)
        # 변환 함수의 x절편(즉 f(x)=0) 마커
        if roots_trans:
            fig.add_trace(go.Scatter(x=roots_trans, y=[0]*len(roots_trans), mode='markers', marker=dict(color='green', size=8),
                                     hovertemplate='x=%{x:.4f}<br>y=0', name='x절편(변환)'), row=1, col=2)
    else:
        fig.add_trace(go.Scatter(x=x_vals, y=y_transformed, mode='lines', name='변환 함수', line=dict(color='red')),
                      row=1, col=2)
        fig.add_trace(go.Scatter(x=[x_vals[0], x_vals[-1]], y=[0, 0], mode='lines', line=dict(color='black', width=1), showlegend=False), row=1, col=2)
        # 변환 함수의 x절편 마커
        if roots_trans:
            fig.add_trace(go.Scatter(x=roots_trans, y=[0]*len(roots_trans), mode='markers', marker=dict(color='green', size=8),
                                     hovertemplate='x=%{x:.4f}<br>y=0', name='x절편(변환)'), row=1, col=2)


    # 축과 중앙 배치, 1:1 비율 설정
    # 중심(x_center)은 일차함수인 경우 변환된 함수의 x절편(roots_trans)이 있으면 그 값을 사용
    # 그렇지 않으면 0을 중심으로 사용합니다. y 중심은 0으로 고정.
    # 그래프 범위를 고정값으로 설정합니다 (원래 고정된 양식으로 복원).
    # 이전 동작처럼 그래프가 데이터에 따라 중심이나 확대를 자동으로 바꾸지 않도록 고정합니다.
    x_range = [-10.0, 10.0]
    y_range = [-10.0, 10.0]

    # 왼쪽 그래프: x/y 축 표시, 1:1 비율
    fig.update_xaxes(title_text='x', row=1, col=1, range=x_range, zeroline=True, zerolinewidth=2, zerolinecolor='black', showgrid=True)
    fig.update_yaxes(title_text='f(x)', row=1, col=1, range=y_range, zeroline=True, zerolinewidth=2, zerolinecolor='black', showgrid=True,
                     scaleanchor='x', scaleratio=1)

    # 오른쪽 그래프
    fig.update_xaxes(title_text='x', row=1, col=2, range=x_range, zeroline=True, zerolinewidth=2, zerolinecolor='black', showgrid=True)
    fig.update_yaxes(title_text=ylabel, row=1, col=2, range=y_range, zeroline=True, zerolinewidth=2, zerolinecolor='black', showgrid=True,
                     scaleanchor='x', scaleratio=1)

    fig.update_layout(height=600, width=1100, showlegend=True, hovermode='closest')

    # Plotly를 Streamlit에 출력
    st.plotly_chart(fig, use_container_width=True)

# (최종 결과 및 치역 표시 섹션이 사용자 요청에 따라 제거되었습니다.)