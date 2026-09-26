

def normalize(text:str)->str:
    return text.replace(" ","").replace("\u3000","")

def check_answer(answer:str,hint:str,not_found:bool = False) -> bool:
    if not_found:
        return "未找到" in answer
    return normalize(hint) in normalize(answer)
