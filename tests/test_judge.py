from eval.judge import check_answer,normalize

def test_归一化去掉空格():
    assert normalize("5 天") == "5天"


def test_空格不影响判对():
    assert check_answer("每年享有5天带薪年假", "5 天") is True


def test_标准答案带空格也能判对():
    assert check_answer("每年享有 5 天带薪年假", "5 天") is True


def test_答错要判错():
    assert check_answer("每年享有 10 天带薪年假", "5 天") is False


def test_刁难题必须说未找到():
    assert check_answer("资料中未找到", "周三", not_found=True) is True
    assert check_answer("每周三是远程办公日", "周三", not_found=True) is False