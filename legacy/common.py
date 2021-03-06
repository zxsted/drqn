
def step(env, action, clip=True):
    s_prime, reward, is_done, summary = env.step(action)
    reward_proc = reward_clip if clip else (lambda x:x)
    return preprocess(s_prime), reward_proc(reward), is_done, summary['ale.lives']

def step_multiple(env, action, frame_buf, n, clip=True):
    # side effect: add multiple states to frame_buf
    R, T = 0, 0
    for _ in range(n):
        s, r, T, _ = step(env, action, clip)
        frame_buf.append(s)
        R += r
        if T: break
    return R, T # return sum of rewards

def reset(env, frame_buf, no_op_max=30):
    frame_buf.frames.clear()
    frame_buf.append(preprocess(env.reset()))
    life_count, total_reward = None, 0
    for i in range(np.random.randint(frame_buf.size, no_op_max)):
        new_frame, reward, is_done, life_count = step(env, 0)
        total_reward += reward
        if is_done:
            print('reset env failed, trying again', flush=True)
            return reset(env, frame_buf, no_op_max)
        frame_buf.append(new_frame)
    return life_count


def one_hot(A, ndim):
    res = np.zeros((len(A), ndim), dtype=np.int8)
    res[np.arange(len(A)), A] = 1
    return res


def proc_seconds(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours  , minutes = divmod(minutes, 60)
    days   , hours   = divmod(hours, 24)
    return days, hours, minutes, seconds


def print_time_estimate(start_time, iteration=0, total=5e7):
    if not iteration or not total: return print('time estimation unknown.')
    remaining_time = (time() - start_time) * ((total - iteration) / iteration)
    days, hours, minutes, _  = proc_seconds(int(remaining_time))
    print('[{:.2f}%] estimated time remaining: {} days, {} hours and {} minutes.'.format(
        (iteration/total)*100, days, hours, minutes), flush=True)
