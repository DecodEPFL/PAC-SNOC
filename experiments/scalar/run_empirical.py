import pickle, sys, os
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.getcwd()))
sys.path.insert(1, BASE_DIR)

from config import device
from assistive_functions import WrapLogger
from experiments.scalar.loss_functions import LQLossFH
from controllers.empirical_controller import *
from experiments.scalar.LTI_sys import LTI_system

random_seed = 33
random_state = np.random.RandomState(random_seed)
logger = WrapLogger(None)


# ------ 1. load data ------
T = 10
S = 16
dist_type = 'N biased'

file_path = os.path.join(BASE_DIR, 'experiments', 'scalar', 'saved_results')
filename = dist_type.replace(" ", "_")+'_data_T'+str(T)+'_RS'+str(random_seed)+'.pkl'
filename = os.path.join(file_path, filename)
if not os.path.isfile(filename):
    print(filename + " does not exists.")
    print("Need to generate data!")
assert os.path.isfile(filename)
filehandler = open(filename, 'rb')
data_all = pickle.load(filehandler)
filehandler.close()
# divide
S_test = None   # use a subset of available test data if not None
data_train = data_all['train_big'][dist_type][:S, :, :]
if not S_test is None:
    data_test = data_all['test_big'][dist_type][:S_test, :, :]
else:
    data_test = data_all['test_big'][dist_type]
# disturbance
disturbance = data_all['disturbance']

# ------ 2. define the plant ------
sys_np = LTI_system(
    A=np.array([[0.8]]),  # num_states*num_states
    B=np.array([[0.1]]),  # num_states*num_inputs
    C=np.array([[0.3]]),  # num_outputs*num_states
    x_init=2*np.ones((1, 1)),  # num_states*1
    use_tensor=False
)
sys = LTI_system(
    sys_np.A, sys_np.B, sys_np.C, sys_np.x_init,
    use_tensor=True
)

# ------ 3. define the loss ------
Q = 5*torch.eye(sys.num_states).to(device)
R = 0.003*torch.eye(sys.num_inputs).to(device)
# optimal loss bound
loss_bound = 1
sat_bound = torch.matmul(torch.matmul(torch.transpose(sys.x_init, 0, 1), Q), sys.x_init)
if loss_bound is not None:
    logger.info('[INFO] bounding the loss to ' + str(loss_bound))
lq_loss_bounded = LQLossFH(Q, R, T, loss_bound, sat_bound, logger=logger)
lq_loss_original = LQLossFH(Q, R, T, None, None, logger=logger)

# ------ 4. Empirical controller ------
batch_size = 5
controller_emp = EmpCont(
    sys=sys, train_d=data_train, lr=0.5, loss=lq_loss_original,
    random_seed=random_seed, optimizer='AdamW')
# fit
controller_emp.fit(num_iter_fit=5000, batch_size=batch_size, log_period=500)

# save empirical
filename = dist_type.replace(" ", "_")+'_emp_T'+str(T)+'_S'+str(S)+'.pkl'
filename = os.path.join(file_path, filename)
filehandler = open(filename, 'wb')
dict_cont = {
    'weight':controller_emp.controller.out.weight.detach().cpu(),
    'bias':controller_emp.controller.out.bias.detach().cpu()
}
pickle.dump(dict_cont, filehandler)
filehandler.close()
logger.info('[INFO] empirical controller with S='+str(S)+' and T='+str(T)+' using random seed'+str(random_seed)+' saved.')
