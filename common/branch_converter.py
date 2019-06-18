def convert_branch(branch):
    """
    Convert release branch to MediaSDK and Media-driver branches

    :param branch: Branch name
    :type branch: String

    :return: MediaSDK branch, Media-driver branch
    :rtype: tuple
    """

    if branch == 'mss2018_r2':
        return branch, 'master'

    if 'sdk' in branch:
        sdk_branch = branch
        driver_branch = branch.replace('sdk', '')
    else:
        sdk_branch = branch.replace('media', 'mediasdk')
        driver_branch = branch

    return sdk_branch, driver_branch
