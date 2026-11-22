"""沿用原实验三TF-IDF入口思想：仅说明fit/predict接口，不作正式性能评价。"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC
train=['高血压如何治疗','失眠如何改善','高血压是什么原因','失眠的诱因是什么']
labels=['治疗方案','治疗方案','病因分析','病因分析']
model=make_pipeline(TfidfVectorizer(analyzer='char',ngram_range=(2,3)),LinearSVC(random_state=20261104))
model.fit(train,labels)
print(model.predict(['失眠应该如何治疗']).tolist())
print('以上4条是虚构接口示例；正式实验应完成公开语料、TF-IDF及小型BERT的完整评价。')
