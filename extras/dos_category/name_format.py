def name(f):
    '''
    Format the file name to be understood in sql
    '''
    text = f.name.split(".sql")[0].replace("-","_") # remove extension and replace -
    text = ''.join(text.split()) # remove spaces
    return ''.join(i for i in text if ord(i)<128) # remove ascii characters