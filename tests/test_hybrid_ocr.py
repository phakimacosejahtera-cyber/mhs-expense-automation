from backend.app.ocr_candidates import combine_observations, enrich_observation, parse_terbilang
from backend.app.paddle_worker import lines_from_result

def test_acer_conflict():
    data=combine_observations({"text":"Total Rp320.000.090","confidence":63},
        {"text":"Total Rp3.200.000\nTiga Juta Dua Ratus Ribu","confidence":90})
    assert parse_terbilang("tiga juta dua ratus ribu")==3200000
    assert not any(x["usable"] for x in data["amount_review"])
    assert data["amount_warnings"]
    assert data["engine_scores"]=={"Tesseract":63,"PaddleOCR":90}

def test_agreement():
    data=combine_observations({"text":"Total Rp3.200.000","confidence":63},
        {"text":"Total Rp3.200.000\nTanggal 20/10/2011","confidence":90})
    assert any(x["usable"] and x["value"]==3200000 for x in data["amount_review"])
    assert data["suggestions"]["dates"]==["2011-10-20"]

def test_unlabelled_amount_blocked():
    data=enrich_observation({"text":"Rp320.000.090","suggestions":{"amounts":[{"value":320000090,"label":"Rp320.000.090"}]}})
    assert not any(x["usable"] for x in data["amount_review"])

def test_paddle_line_join():
    text,scores=lines_from_result({"rec_texts":["Total","Rp3.200.000"],"rec_scores":[.9,.8],
        "rec_polys":[[[0,0],[50,0],[50,20],[0,20]],[[65,0],[180,0],[180,20],[65,20]]]})
    assert "Total Rp3.200.000" in text
    assert scores==[.9,.8]
