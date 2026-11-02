`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2026/10/05 17:42:52
// Design Name: 
// Module Name: RGB888toRGB565
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module rgb888torgb565(
    input [23:0]RGB888,
    output [15:0]RGB565
);
    
    wire [4:0]Red;
    wire [5:0]Green;
    wire [4:0]Blue;
    
    assign Red   = RGB888[23:19];
    assign Green = RGB888[15:10];
    assign Blue  = RGB888[ 7: 3];
    
    assign RGB565= {Red,Green,Blue};
endmodule
