#!/usr/bin/env python3
import sys, os, subprocess

def try_run(cmd):
	if os.system(cmd) != 0:
		sys.exit(1)


def merge(f1, f2, from_, to):
	"""
	Merges lines from line containting 'from_' to line containing 'to'
	from f1 to f2
	"""
	lines1, inside = [], False
	with open(f1, "r") as fh1:
		for line in fh1.readlines():
		if from_ in line.strip("\r\n\t "):
			inside = True
		elif to in line.strip("\r\n\t "):
			inside = False
		if inside:
			lines1.append(line)

	lines2, inside = [], False
	with open(f2, "r") as fh2:
		for line in fh2.readlines():
		if from_ in line.strip("\r\n\t "):
			inside = True
			lines2 += lines1
		elif to in line.strip("\r\n\t "):
			inside = False
		elif not inside:
			lines2.append(line)

	with open(f2, "w") as fh2:
		fh2.write("".join(lines2))


def main():

	if not os.path.exists("sc-controller.wiki/.git"):
		try_run("git clone 'https://github.com/andersmmg/sc-controller.wiki.git'")

	os.chdir("sc-controller.wiki")
	try_run("git pull")
	try_run("git reset master")

	merge(
		'../docs/actions.md',
		'Custom-Action-Examples-and-Explanations.md',
		'# <a name="actions">',
		'# <a name="examples2">'
	)

	try_run("git commit -a -m \"Updated wiki from docs\"")


if __name__ == "__main__":
	main()
