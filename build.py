import os, sys, re
from optparse import OptionParser
import subprocess
    
def safe_rmtree(path):
    # count damage, I dont trust this script at all :)
    damage = 0
    for root, dirs, files in os.walk(path):
        damage += len(files) + len(dirs)
    if damage > 100:
        raise Exception('potential damage, aborted')
    #print '!! Deleting everything from temp path %s/ in 5 seconds ...' % path
    #time.sleep(5)
    #shutil.rmtree(path)
    rmtree(path)
    
def rmtree(path) :
    """shutil.rmtree with verbosity"""
    for name in os.listdir(path):
        file = os.path.join(path, name)
        if not os.path.islink(file) and os.path.isdir(file):
            rmtree(file)
        else:
            print 'rm %s' % file
            os.remove(file)
    os.rmdir(path)
    return
    
if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-r', '--rev',
                      action='store', type='int', dest='rev', default=0,
                      help='Build specific revision', metavar='FILE')
                      
    parser.add_option('-p', '--path',
                      action='store', dest='path', default='http://svn.flexget.com/trunk',
                      help='SVN repository path')

    parser.add_option('-z', '--zip',
                      action='store', dest='zip', default='/var/www/flexget_dist',
                      help='Path for a zip')
                      
    parser.add_option('-t', '--tag',
                      action='store', dest='tag', default=None,
                      help='Tag package name, used instead revision')

    (options, args) = parser.parse_args()
    
    if options.zip[-1:] == '/':
        options.zip = options.zip[:-1]
    
    # export from svn and get revision
    export_path = sys.path[0] + '/flexget'
    export_cmd = ['svn', 'export']
    if options.rev > 0:
        export_cmd.extend(['-r', options.rev])
    export_cmd.append(options.path)
    export_cmd.append(export_path)
    print export_cmd
    proc = subprocess.Popen(export_cmd, stdout=subprocess.PIPE)
    out = proc.communicate()[0]
    m = re.search('Exported revision (\d+)', out)
    #print out
    if not m:
        raise Exception('no rev found from svn export?')
    rev = m.groups()[0]
    
    # rename and remove some files
    os.rename('%s/example.yml' % export_path, '%s/config.yml' % export_path)
    os.remove('%s/quality_check.sh' % export_path)
    os.remove('%s/build.py' % export_path)
    
    # make a zip
    if not options.tag:
        package_name = '%s/FlexGet_(r%s).zip' % (options.zip, rev)
    else:
        package_name = '%s/FlexGet_%s.zip' % (options.zip, options.tag)
    zip_cmd = ['7z', 'a', '-tzip', package_name, export_path]
    subprocess.call(zip_cmd)
   
    # remove working directory
    safe_rmtree(export_path)
    
    if not os.path.exists(package_name):
        print '!! FAILED to create %s' % package_name
    else:
        print 'Created: %s' % package_name