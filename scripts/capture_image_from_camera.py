import cv2

cam_port = 0
cam = cv2.VideoCapture(cam_port)

# Check if the camera is opened successfully
if not cam.isOpened():
    print("Error: Unable to open camera")
    exit()

# Reading the input using the camera
inp = input('Enter person name: ')

# If image is detected without any error, show result
while True:
    ret, image = cam.read()
    
    # Check if the image is captured successfully
    if not ret:
        print("Error: Failed to capture image")
        break

    cv2.imshow('Captured Image', image)
    
    key = cv2.waitKey(1) & 0xFF  # Wait for key press event for 1 millisecond
    if key == ord('s'):  # Press 's' to save the image
        image_path = f'./images/{inp}.png'
        cv2.imwrite(image_path, image)
        print("Image taken")
        break  # Exit the loop after capturing the image
    elif key == 27:  # Press 'Esc' to exit without saving
        break

# Release the camera and close all OpenCV windows
cam.release()
cv2.destroyAllWindows()
