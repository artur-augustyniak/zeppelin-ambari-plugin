import sys, os, pwd, grp, signal, time, glob
from resource_management import *
from subprocess import call

class Master(Script):

  def install(self, env):

    import params
    import status_params

    # Create user and group if they don't exist
    self.create_linux_user(params.zeppelin_user, params.zeppelin_group)
    self.create_hdfs_user(params.zeppelin_user)

    # create the log dir if it not already present
    Directory([params.zeppelin_pid_dir, params.zeppelin_log_dir],
        owner=params.zeppelin_user,
        group=params.zeppelin_group,
        recursive=True
    )

    Execute('touch ' + params.zeppelin_log_file, user=params.zeppelin_user)    
    Execute('rm -rf ' + params.zeppelin_dir, ignore_failures=True)
    Execute('mkdir ' + params.zeppelin_dir)
    Execute('chown -R ' + params.zeppelin_user + ':' + params.zeppelin_group + ' ' + params.zeppelin_dir)
    
    self.install_packages(env)    
    
    # Fetch and unzip snapshot build, if no cached zeppelin tar package exists on Ambari server node
    if not os.path.exists(params.temp_file):
      Execute('wget ' + params.zeppelin_tarball_url + ' -O ' + params.temp_file + ' -a ' + params.zeppelin_log_file, user=params.zeppelin_user)

    Execute('tar -zxvf ' + params.temp_file + ' -C ' + params.zeppelin_dir + ' >> ' + params.zeppelin_log_file, user=params.zeppelin_user)
    Execute('mv ' + params.zeppelin_dir + '/*/* ' + params.zeppelin_dir, user=params.zeppelin_user)
    
    Execute('wget ' + params.zeppelin_notebooks_url + ' -O ' + params.notebook_dir + '/notebooks.tar.gz', user=params.zeppelin_user)
    Execute('tar -zxvf ' + params.notebook_dir + '/notebooks.tar.gz -C ' + params.zeppelin_dir + ' >> ' + params.zeppelin_log_file, user=params.zeppelin_user)
    
    # update the configs specified by user
    self.configure(env)
        
  def create_linux_user(self, user, group):
    try: pwd.getpwnam(user)
    except KeyError: Execute('adduser ' + user)
    try: grp.getgrnam(group)
    except KeyError: Execute('groupadd ' + group)

  def create_hdfs_user(self, user):
    Execute('hadoop fs -mkdir -p /user/' + user, user='hdfs', ignore_failures=True)
    Execute('hadoop fs -chown ' + user + ' /user/' + user, user='hdfs')
    Execute('hadoop fs -chgrp ' + user + ' /user/' + user, user='hdfs')

  def configure(self, env):
    import params
    import status_params
    env.set_params(params)
    env.set_params(status_params)
    
    # write out zeppelin-site.xml
    XmlConfig("zeppelin-site.xml",
            conf_dir=params.conf_dir,
            configurations=params.config['configurations']['zeppelin-config'],
            owner=params.zeppelin_user,
            group=params.zeppelin_group
    ) 
    # write out zeppelin-env.sh
    env_content = InlineTemplate(params.zeppelin_env_content)
    File(format("{params.conf_dir}/zeppelin-env.sh"), content=env_content, owner=params.zeppelin_user, group=params.zeppelin_group)  # , mode=0777)    
    
    # run setup_snapshot.sh in configure mode to regenerate interpreter and add back version flags 
    service_packagedir = os.path.realpath(__file__).split('/scripts')[0]

  def stop(self, env):
    import params
    import status_params

    Execute (params.zeppelin_dir + '/bin/zeppelin-daemon.sh stop >> ' + params.zeppelin_log_file, user=params.zeppelin_user)

  def start(self, env):
    import params
    import status_params
    self.configure(env) 
    
    note_osx_dir = params.notebook_dir + '/__MACOSX'   
    if os.path.exists(note_osx_dir):
      Execute('rm -rf ' + note_osx_dir)
    
    Execute (params.zeppelin_dir + '/bin/zeppelin-daemon.sh start >> ' + params.zeppelin_log_file, user=params.zeppelin_user)
    pidfile = glob.glob(status_params.zeppelin_pid_dir + '/zeppelin-' + params.zeppelin_user + '*.pid')[0]
    Execute('echo pid file is: ' + pidfile, user=params.zeppelin_user)
    contents = open(pidfile).read()
    Execute('echo pid is ' + contents, user=params.zeppelin_user)

  def status(self, env):
    import status_params
    env.set_params(status_params) 
    pid_file = glob.glob(status_params.zeppelin_pid_dir + '/zeppelin-' + status_params.zeppelin_user + '*.pid')[0]
    check_process_status(pid_file)
      
if __name__ == "__main__":
  Master().execute()
