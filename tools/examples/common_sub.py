import re
def clean(txt):
    R=[(r'\s*\[\d+(?:,\s*\d+)*\]',''),(r'ł|ž','"'),(r'’','\''),(r'“|”','"'),(r'ś','–'),(r'Ð',' – '),
       (r'𝑝','p'),(r'𝛼','alpha'),(r'𝐷','D'),(r'≈\s?','about '),(r'(\d) (\d{3})\b',r'\1\2'),
       (r'\bRQ ?(\d)\b',r'research question \1'),(r'\bAECs\b','A E Cs'),(r'\bAEC\b','A E C'),(r'\bAE\b','A E'),
       (r'\bACM\b','A C M'),(r'\bICSE\b','I C S E'),(r'\bESEC/FSE\b','F S E'),(r'\bFSE\b','F S E'),(r'\bASE\b','A S E'),(r'\bISSTA\b','I S S T A'),
       (r'\bNonAE\b','non-A E'),(r'\bNoB\b','N o B'),(r'\bNoA\b','N o A'),(r'\bAv\.','Av'),(r'\bDL\b','D L'),(r'\bSE\b','S E'),(r'\bPL\b','P L'),
       (r'\bKS\b','K S'),(r'\bBH\b','B H'),(r'\bOA\b','O A'),(r'\bCA\b','C A'),(r'\bURLs\b','U R Ls'),(r'\bURL\b','U R L'),(r'\bHTTP\b','H T T P'),(r'\bVCS\b','version control'),
       (r'\bDOIs?\b','D O I'),(r'\bCCS\b','C C S'),(r'\bNDSS\b','N D S S'),(r'S&P','S and P'),(r'\bUSENIX\b','Usenix'),(r'\bML\b','M L'),(r'\bVMs\b','V Ms'),(r'\bVM\b','V M'),
       (r'\bGPUs\b','G P Us'),(r'\bCPU\b','C P U'),(r'\bH 0\b','H nought'),(r'\bReadMe\'s\b','read-mes'),(r'\bReadMes?\b','read-me'),(r'\bReadme\b','read-me'),(r'\bREADME\b','read-me'),
       (r'κ = ','kappa equals '),(r'p < 0\.005','p below 0.005'),(r'p < 0\.05','p below 0.05'),(r'0\.005 < p < 0\.05','p between 0.005 and 0.05'),(r'p = ','p equals '),
       (r'\(cf\.[^)]*\)',''),(r'(\d+(?:\.\d+)?)\s?%',r'\1 per cent'),(r'\$1,000','1000 dollar'),(r'⇒','implies'),(r'e\.g\.,?','for example'),(r'i\.e\.,?','that is'),(r'\betc\b\.?','and so on'),
       (r' {2,}',' '),(r'\s+([,.;:])',r'\1'),(r'\.\.',r'.')]
    for a,b in R: txt=re.sub(a,b,txt,flags=re.M)
    return txt
