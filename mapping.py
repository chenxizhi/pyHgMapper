"""
Mapping utils used for mapping chromosome coordinates to genes or other gene elements.

Created on 5/4/2014
"""
from annotations import *
from classes import *

import os, sys
import argparse as ap
import datetime as dt
from collections import Counter
import cookielib, urllib2
## dependency:
import poster
import pygal as pg

def read_indel(fn):
	'''read indels from .indel file into a list of Indels'''
	indels = []
	with open (fn) as f:
		for line in f:
			if not line.startswith('#'):
				sl = line.strip().split('\t')
				chrom = 'chr'+sl[2]
				refStart = int(float(sl[6]))
				refEnd = int(float(sl[7]))
				confidence = float(sl[9])
				typeStr = sl[10]
				coordinates = [chrom, refStart, refEnd]
				indel = Indel(coordinates, confidence, typeStr)
				indels.append(indel)
	return indels

def read_indel_xmap_iter (fn):
        indels = []
	with open (fn) as f:
		for line in f:
			if not line.startswith('#'):
				sl = line.strip().split('\t')
				chrom = 'chr'+sl[2]
				refStart = int(float(sl[6]))
				refEnd = int(float(sl[7]))
				confidence = float(sl[9])
				typeStr = sl[10]
				coordinates = [chrom, refStart, refEnd]
				indel = Indel(coordinates, confidence, typeStr)
				yield indel

def read_indel_iter(fn):
	"""yield generator for Indels if the file is large"""
	print "entering read indel iter"
	if ".bed" == fn[-4:]:
                return read_indel_bed_iter(fn)
        else:
                return read_indel_xmap_iter (fn)
	
                

def read_indel_bed_iter(fn):
	"""yield generator for Indels if the file is large"""
	print "entering read indel bed iter"
	indels = []
	with open (fn) as f:
		for line in f:
			if not line.startswith('#'):
				sl = line.strip().split('\t')
				chrom = sl[0][3:]
				if chrom == "X":
                                        chrom = 23
                                if not chrom in (map(str, range(1, 24))):
                                        continue
                                chrom = "chr"+chrom
				refStart = int(float(sl[1]))
				refEnd = int(float(sl[2]))
				confidence = 10
				typeStr = "deletion"
				coordinates = [chrom, refStart, refEnd]
				indel = Indel(coordinates, confidence, typeStr)
				yield indel

def mapping(indel_fn, annotation_fn='knownGenes.txt'):
	'''a  function for mapping indels to genes'''
	genes = load_annotations(annotation_fn)
	# print 'Number of genes in the referrence genome: ', len(genes)
	## counters:
	a = 0 # indel count
	b = 0 # indels mapped to genes
	c = 0 # indels mapped to CDS
	d = 0 # indels mapped to exons
	genes_indel = {} # genes with insertion/deletion
	print "indel fn: %s" %(indel_fn)
	for indel in read_indel_iter(indel_fn):
		a += 1
		position = indel.position
		chrom = indel.chrom
		if chrom == 'chr23':
			chrom = 'chrX'
		mapped_g = False # whether mapped to genes
		mapped_cds = False
		for gene in genes[chrom]:
			if position in gene:
				mapped_g = True
				gene_name = gene.name
				genes_indel[gene_name] = [indel.typeStr, 'gene']
				if position in gene.CDS:
					mapped_cds = True
					genes_indel[gene_name][1] = 'CDS'
					for exon in gene.exons:
						if position in exon:
							genes_indel[gene_name][1] = 'exon'
							d += 1
							break
		if mapped_g:
			b += 1
		if mapped_cds:
			c += 1
	return genes_indel, a, b, c, d

def format_gene_sets(genes_indel):
	"""convert the genes_indel dictionary to a gene-set library format"""
	d_term_genes = {}
	# gene_element_levels = ['gene', 'CDS', 'exon']
	# indel_types = ['insertion', 'deletion']
	for gene in genes_indel:
		term = '_'.join(genes_indel[gene])
		if term not in d_term_genes:
			d_term_genes[term] = [gene]
		else:
			d_term_genes[term].append(gene)
	return d_term_genes
		
def d2gmt(d, gmtfn):
	"""write a dictionary into gmt file format"""
	with open (gmtfn, 'w') as out:
		for term in d:
			out.write(term + '\tna\t')
			out.write('\t'.join(d[term]) + '\n')
	return

def enrichr_link(genes, meta=''):
	"""post a gene list to enrichr server and get the link."""
	cj = cookielib.CookieJar()
	opener = poster.streaminghttp.register_openers()
	opener.add_handler(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))

	params = {'list':genes,'description':meta}
	datagen, headers = poster.encode.multipart_encode(params)
	url = "http://amp.pharm.mssm.edu/Enrichr/enrich"
	request = urllib2.Request(url, datagen, headers)
	urllib2.urlopen(request)

	x = urllib2.urlopen("http://amp.pharm.mssm.edu/Enrichr/share")
	response = x.read()
	split_strings = response.split('"')
	linkID = split_strings[3]
	share_url_head = "http://amp.pharm.mssm.edu/Enrichr/enrich?dataset="
	link = share_url_head + linkID
	return link

def genomic_distribution(indel_fn):
	"""get chromosome distribution of insertion and deletion"""
	print 'Calculating genomic distribution statistics'
	chroms_i = []
	chroms_d = []
	for indel in read_indel_iter(indel_fn):
		chrom = int(indel.chrom[3:]) # convert chrom to int
		if indel.typeStr == 'insertion':
			chroms_i.append(chrom)
		else:
			chroms_d.append(chrom)
	if len(chroms_i) == 0:
                c_chroms_i = Counter()
        else:
        	c_chroms_i = Counter(chroms_i)
        if len(chroms_d) == 0:
                c_chroms_d = Counter()
        else:
        	c_chroms_d = Counter(chroms_d)
	return c_chroms_i, c_chroms_d


def plot_pie(a, b, c, d):
        print >>sys.stderr, "a: %s, b: %s, c: %s, d: %s" %(a, b, c, d)
	a = float(a)
	pie_chart = pg.Pie()
	pie_chart.title = 'Indels mapped to genomic elements (in %)'
	pie_chart.add('Intergenic', 100*(a-b)/a)
	pie_chart.add('Gene (non-coding region)', 100*(b-c)/a)
	pie_chart.add('Exon', 100*d/a)
	pie_chart.add('Intron', 100*(c-d)/a)
	pie_chart.render_to_file('indel_gene_element_mapping.svg')
	return


def plot_bars(c_chroms_i, c_chroms_d):
	"""bar plots for chromosome distribution of INDELs"""
	bar_plot = pg.Bar(spacing=0, x_title='Chromosomes', y_title='Number of INDELs')
	bar_plot.title = 'Chromosome distribution of INDELs'
	chroms = c_chroms_i.keys()
	chroms.sort()
	bar_plot.x_labels = map(str, chroms)
	bar_plot.add('Insertion', [c_chroms_i[x] for x in chroms])
	bar_plot.add('Deletion', [c_chroms_d[x] for x in chroms])
	bar_plot.add('INDELs', [c_chroms_i[x] + c_chroms_d[x] for x in chroms])
	bar_plot.render_to_file('chromosome_distribution.svg')
	return

def write_output(indel_fn, d_term_genes, a, b, c, d):
	"""write the running infomation and results into a txt file"""
	outfn = indel_fn[0:-6] + '.out'
	with open (outfn, 'w') as out:
		## overall summary statistics:
		out.write('Summary statistics: \n')
		out.write('-'*8 + '\n')
		out.write('Total Number of INDELs: %s\n'%a)
		out.write('INDELs mapped to genes: %s\n'%b)
		out.write('INDELs mapped to CDS: %s\n'%c)
		out.write('INDELs mapped to exons: %s\n'%d)
		out.write('\n')
		## write Enrichr links:
		out.write('Enrichment analysis for INDELs affected genes: \n')
		out.write('-'*8 + '\n')
		print 'Performing enrichment analysis for the gene lists'
		for term in d_term_genes:
			link = enrichr_link(d_term_genes[term], meta=term)
			out.write(term + ':\t' + link + '\n')
	return

def output_wraper(indel_fn, d_term_genes, a, b, c, d):
	c_chroms_i, c_chroms_d = genomic_distribution(indel_fn)
	try:
		os.mkdir('output')
	except:
                print >>sys.stderr, "was not able to create directory, output"
		pass
	os.chdir('./output')
	write_output(indel_fn, d_term_genes, a, b, c, d)
	d2gmt(d_term_genes, 'genes_affected_by_indels.gmt')
	plot_pie(a, b, c, d)
	plot_bars(c_chroms_i, c_chroms_d)
	pwd = os.getcwd()
	print "All results are stored in %s" % pwd
	return 

def main():
	## parsing argvs
	parser = ap.ArgumentParser()
	parser.add_argument('indel filename', help='the name of the indel file', type=str)
	parser.add_argument('-a','--annotation', help='the name of gene annotation file name', default='knownGenes.txt', type=str)
	args = vars(parser.parse_args())
	indel_fn = args['indel filename']
	annotation_fn = args['annotation']

	start_time = dt.datetime.now()
	print 'Thank you for using pyHgMapper'
	print start_time
	print '-'*10
	print 'Mapping INDELs in %s to genome' % indel_fn
	## map indels:
	genes_indel, a, b, c, d = mapping(indel_fn, annotation_fn=annotation_fn)
	d_term_genes = format_gene_sets(genes_indel)
	## output results:
	output_wraper(indel_fn, d_term_genes, a, b, c, d)
	end_time = dt.datetime.now()
	print end_time
	print 'time elapsed: ', end_time - start_time
	return

if __name__ == '__main__': ## potentially make this a cmd line tool
	main()
