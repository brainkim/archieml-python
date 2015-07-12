from loader import Loader

def load(aml):
	loader = Loader()
	return loader.load(aml)

def load_file(f):
	return load(f.read())
