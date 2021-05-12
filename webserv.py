import sys
import socket
import os
import gzip


"""Parses the config file and returns a dictionary containing the config info"""
def read_config(filename):

	f = ""
	try:
		f = open(filename, "r")
	except FileNotFoundError:
		print("Unable To Load Configuration Argument")
		quit()

	config = {}
	counter = 0

	for line in f:
		counter += 1
		split_line = line.split("=")
		config[split_line[0].strip()] = split_line[1].strip()  # Adds config variable to dictionary
	
	f.close()
	
	if counter != 4:
		print("Missing Field From Configuration File")
		quit()

	return config


"""Retrieves all static files present in directory and subdirectories provided"""
def retrieve_static_files(directory):

	file_types = ["txt", "html", "js", "css", "png", "jpg", "jpeg", "xml"]
	contents = os.listdir(path=directory)
	files = []

	for element in contents:
		filepath = os.path.join(directory, element)  # Gets filepath of file

		if os.path.isdir(filepath):  # If the current element is a directory, recursively call the function to get all the files in it
			files = files + retrieve_static_files(filepath)
		else: # add file to list
			files.append(filepath)
		
	filtered_files = []

	for file in files:
		if file.split(".")[-1] in file_types:  # Makes sure the file is a valid filetype
			filtered_files.append(file)

	return filtered_files


"""Extracts name of file from request"""
def parse_static_request(request):

	request_split = request.split(" ")
	file_requested = request_split[1].lstrip("/")
	return file_requested


"""Determines content-type of given file"""
def get_filetype(filename):

	filetype = ""

	if filename.endswith(".txt"):
		filetype = "text/plain"

	elif filename.endswith(".html"):
		filetype = "text/html"

	elif filename.endswith(".js"):
		filetype = "application/javascript"

	elif filename.endswith(".css"):
		filetype = "text/css"

	elif filename.endswith(".png"):
		filetype = "image/png"

	elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
		filetype = "image/jpeg"

	elif filename.endswith(".xml"):
		filetype = "text/xml"
	
	return filetype


"""Reads contents of static file and constructs server response"""
def process_static_request(filename ,file_list, configuration):

	if filename == "":  # Special case if no file is specified
		filename = "index.html"
	
	filetype = get_filetype(filename)

	header = ""
	response = "".encode()
	content_type = "".encode()
	f = ""
	file_exists = False

	try:
		for file_path in file_list:  # Checks if the file exists
			if filename in file_path:
				file_exists = True

		if file_exists == False:
			raise FileNotFoundError
		
		filepath = configuration["staticfiles"] + "/" + filename
		f = open(filepath, "rb")

		for line in f:  # Constructs content response
			response += line

		f.close()

		header = ("HTTP/1.1 200 OK\n").encode()
		content_type = ("Content-Type: " + filetype + "\n\n").encode()

	except FileNotFoundError:
		header = "HTTP/1.1 404 File not found\n".encode()
		content_type = "Content-Type: text/html\n\n".encode()
		response = '<html>\n<head>\n\t<title>404 Not Found</title>\n</head>\n<body bgcolor="white">\n<center>\n\t<h1>404 Not Found</h1>\n</center>\n</body>\n</html>\n'.encode()

	response_to_send =  [header, content_type, response]
	return response_to_send


"""Parses the CGI request, sets the environment variables and returns file requested"""
def parse_cgi_request(request):

	valid_headers = {
			"Accept" : "HTTP_ACCEPT",
			"Host" : "HTTP_HOST",
			"User-Agent" : "HTTP_USER_AGENT",
			"Accept-Encoding" : "HTTP_ACCEPT_ENCODING",
			"Remote-Address" : "REMOTE_ADDRESS",
			"Content-Type" : "CONTENT_TYPE",
			"Content-Length" : "CONTENT_LENGTH"
			}

	request_split = request.split("\n")

	if "?" in request:  # Extracts query string
		query = request_split[0].split("?")
		os.environ["QUERY_STRING"] = query[1].split(" ")[0]
	
	i = 1
	while i<len(request_split):  # Iterates through request and sets appropriate environment variables
		if request_split[i].split(":")[0] in valid_headers:
			for header in valid_headers:
				if header == request_split[i].split(":")[0]:
					os.environ[valid_headers.get(header)] = request_split[i].split(":")[1]
		i += 1

	os.environ["REQUEST_METHOD"] = request_split[0].split(" ")[0]
	os.environ["REQUEST_URI"] = request_split[0].split(" ")[1]

	file_requested = request_split[0].split(" ")[1].split("/")[-1]

	return file_requested.split("?")[0]  # Catches case where query string is attatched


"""Runs the CGI script"""
def run_cgi_program(file, configuration):

	r,w = os.pipe()
	pid = os.fork()

	if pid == 0:  # Child process
		try:

			os.close(r)  # Closes descriptor it doesn't use
			os.dup2(w, 1)  # Replaces w with it's own standard output

			filepath = configuration["cgibin"] + "/" + file
			os.execle(configuration["exec"],'python3', filepath, os.environ)

		except OSError:  # Catches any potential error with the execution of the program
			sys.exit(1)  # Exits with non-zero exit status to indicate error in child process

	elif pid > 0:  # Parent process

		os.close(w)  # Closes descriptor it is not using
		exit_status = os.wait()  # Waits for the child

	return process_child_output(exit_status, r)


"""Reads output of the child and constructs server response"""
def process_child_output(exit_status, descriptor):

	if int(exit_status[1]) != 0:  # If there was an error in the child
		return ["HTTP/1.1 500 Internal Server Error\n".encode(), "".encode(), "".encode()]

	f = os.fdopen(descriptor, "r")  # Opens the file descriptor for reading - allows access to child's output
	return_string = ""
	header = ""

	content_type_exists = False
	custom_header_exists = False

	for line in f:

		if "Content" in line:  # Checks if child already outputs it's own content type
			content_type_exists = True
		if "Status" in line:  # Checks if child has it's own custom status
			custom_header_exists = True
			header = ("HTTP/1.1 " + line.split(": ")[1]).encode()
			continue
		return_string += line  # Constructs server's content response

	f.close()

	if content_type_exists == False:  # Manually creates content-type to send if it doesn't exist in the child output
		content_type = "Content-Type: text/html\n\n".encode()
	else:
		content_type = "".encode()

	if custom_header_exists == False:  # Manually creates header to send if it doesn't exist in the child output
		header = ("HTTP/1.1 200 OK\n").encode()

	return [header, content_type, return_string.encode()]


"""Main loop of the program"""
def main():

	if len(sys.argv) < 2:
		print("Missing Configuration Argument")
		quit()
	
	config_file = sys.argv[1]
	configuration = read_config(config_file)  # Is a dictionary
	static_files = retrieve_static_files(configuration["staticfiles"])

	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allows address to be reused
	address = ("127.0.0.1", int(configuration["port"]))
	sock.bind(address)
	sock.listen()

	os.environ["SERVER_ADDR"] = "127.0.0.1"
	os.environ["SERVER_PORT"] = configuration["port"]

	while True:

		client = sock.accept()
		client_socket = client[0]
		client_address = client[1][0]
		client_port = client[1][1]

		os.environ["REMOTE_ADDRESS"] = str(client_address)
		os.environ["REMOTE_PORT"] = str(client_port)

		request = client_socket.recv(1024).decode("utf-8")

		pid = os.fork()

		if pid == 0:  # Child process will handle the request to allow for concurrent connections

			if configuration["cgibin"].split("/")[-1] not in request:  # Static requests
				response = process_static_request(parse_static_request(request),static_files, configuration)

			else:  # CGI requests
				response = run_cgi_program(parse_cgi_request(request), configuration)

			"""EXTENSION: Compresses the contents of the static file using gzip so it can be sent to the client"""
			if "Accept-Encoding: gzip" in request:  # Gzip requests - checks that the client is requesting gzip
				data_to_zip = response[2]
				response[2] = gzip.compress(data_to_zip)
			
			client_socket.send(response[0])
			client_socket.send(response[1] + response[2])

			client_socket.close()

		elif pid > 0:  # Parent terminates client connection so it can receive another one
			client_socket.close()
			continue


if __name__ == '__main__':
	main()
