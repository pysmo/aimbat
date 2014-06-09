import unittest
import sys
sys.path.append('aimbat')

class InterfaceTests(unittest.TestCase):

	def backButton(self):
		typeOf = zipFile('lol')
		print 'yoloswag'
		self.failIf(typeOf=='')

	def lol(self):
		self.failUnless(1==2)


def main():
	unittest.main()

if __name__ == '__main__':
	main()